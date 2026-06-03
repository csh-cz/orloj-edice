# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Client for the Transkribus TrpServer REST API.

Authentication uses readcoop SSO (OAuth2 password grant). The resulting access
token carries the ``TrpServer`` audience and is sent as a Bearer header — this is
the API path available to a normal Transkribus account (the same one the desktop
"eXpert" client uses; HTR consumes the account's regular credits).

Note: the separately-billed Metagrapho "Processing API" needs a different token
audience that a normal password-grant login does not get, so it is NOT used here.

Endpoints verified live against the account:
  GET  /collections/list
  GET  /recognition/{collId}/list           (HTR models usable in a collection)
  GET  /models/text                         (global text-model catalogue)
  POST /uploads                             (create document from images)
  PUT  /uploads/{uploadId}                  (upload one page image)
  POST /pylaia/{collId}/{modelId}/recognition   (neural "text" model HTR)
  POST /recognition/{collId}/{htrId}/htrCITlab  (legacy CITlab HTR)
  GET  /jobs/{jobId}
  GET  /collections/{collId}/{docId}/fulldoc
  GET  /collections/{collId}/{docId}/{pageNr}/curr  (current transcript metadata)
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path

import httpx

from transcribus.transkribus.models import Collection, Document, HtrModel, Job, JobStatus

OIDC_TOKEN_URL = (
    "https://account.readcoop.eu/auth/realms/readcoop/protocol/openid-connect/token"
)
OIDC_CLIENT_ID = "processing-api-client"
DEFAULT_BASE_URL = "https://transkribus.eu/TrpServer/rest"


class TranskribusError(RuntimeError):
    pass


class TranskribusClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 120.0,
        http: httpx.Client | None = None,
    ) -> None:
        self._http = http or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        self._logged_in = False
        self._creds: tuple[str, str, str | None] | None = None
        self._token_deadline = 0.0  # time.monotonic() after which the token is refreshed
        self._refresh_token: str | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> TranskribusClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- auth -------------------------------------------------------------
    def login(self, user: str, password: str, *, otp: str | None = None) -> None:
        """Authenticate via readcoop SSO (OAuth2 password grant) and set Bearer token.

        Access tokens are short-lived (~5 min); credentials are kept so the token
        can be refreshed automatically during long runs (LA + HTR over many pages).
        """
        self._creds = (user, password, otp)
        self._authenticate()

    def _authenticate(self) -> None:
        user, password, otp = self._creds  # type: ignore[misc]
        data = {
            "grant_type": "password",
            "username": user,
            "password": password,
            "client_id": OIDC_CLIENT_ID,
            "scope": "offline_access",
        }
        if otp:
            data["totp"] = otp
        resp = httpx.post(OIDC_TOKEN_URL, data=data, timeout=30.0)
        if resp.status_code != 200:
            raise TranskribusError(
                f"SSO login failed ({resp.status_code}): {resp.text[:300]}\n"
                "Hint: if you sign in via Google/institutional SSO, set a password at "
                "account.readcoop.eu; if you use 2FA, pass an OTP."
            )
        tok = resp.json()
        self._http.headers["Authorization"] = f"Bearer {tok['access_token']}"
        self._refresh_token = tok.get("refresh_token")
        # Refresh ~30s before the access token actually expires.
        self._token_deadline = time.monotonic() + float(tok.get("expires_in", 300)) - 30
        self._logged_in = True

    def _ensure_token(self) -> None:
        if self._creds and time.monotonic() >= self._token_deadline:
            self._authenticate()

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Single choke point for HTTP calls: refresh the token first, retry once on 401."""
        self._ensure_token()
        resp = self._http.request(method, url, **kwargs)
        if resp.status_code == 401 and self._creds:
            self._authenticate()
            resp = self._http.request(method, url, **kwargs)
        return resp

    # -- collections / models / documents --------------------------------
    def list_collections(self) -> list[Collection]:
        data = self._get_json("/collections/list")
        return [Collection(coll_id=int(c["colId"]), name=c.get("colName", "")) for c in data]

    def list_models(self, coll_id: int) -> list[HtrModel]:
        """HTR models usable in a collection (GET /recognition/{collId}/list)."""
        data = self._get_json(f"/recognition/{coll_id}/list")
        return [
            HtrModel(
                model_id=int(m.get("htrId") or m.get("modelId")),
                name=m.get("name", ""),
                model_type=m.get("type", ""),
                language=m.get("language", ""),
                provider=m.get("provider", ""),
            )
            for m in data
        ]

    def list_documents(self, coll_id: int) -> list[Document]:
        data = self._get_json(f"/collections/{coll_id}/list")
        return [
            Document(
                doc_id=int(d["docId"]),
                title=d.get("title", ""),
                n_pages=int(d.get("nrOfPages", 0) or 0),
            )
            for d in data
        ]

    # -- upload (create document from images) -----------------------------
    def create_document(self, coll_id: int, title: str, images: Iterable[Path]) -> int:
        """Create a document in a collection from local images; return its docId."""
        images = list(images)
        pages = [{"fileName": p.name, "pageNr": i + 1} for i, p in enumerate(images)]
        body = {"md": {"title": title}, "pageList": {"pages": pages}}
        upload = self._as_json(
            self._request(
                "POST",
                "/uploads",
                params={"collId": coll_id},
                json=body,
                headers={"Content-Type": "application/json"},
            )
        )
        upload_id = int(upload["uploadId"])

        for p in images:
            with p.open("rb") as fh:
                self._as_json(
                    self._request(
                        "PUT",
                        f"/uploads/{upload_id}",
                        files={"img": (p.name, fh, "image/jpeg")},
                    )
                )

        return self._resolve_uploaded_doc(upload_id, coll_id, title)

    def _resolve_uploaded_doc(self, upload_id: int, coll_id: int, title: str) -> int:
        # The upload reports docId = -1 until its ingest job creates the document;
        # poll until a real (> 0) id appears, then fall back to a title lookup.
        for _ in range(90):
            status = self._get_json(f"/uploads/{upload_id}")
            doc_id = status.get("docId") or (status.get("md") or {}).get("docId")
            if doc_id and int(doc_id) > 0:
                return int(doc_id)
            time.sleep(2)
        for doc in self.list_documents(coll_id):
            if doc.title == title:
                return doc.doc_id
        raise TranskribusError(f"Upload {upload_id} finished but docId could not be resolved")

    # -- FTP ingest -------------------------------------------------------
    def ingest_from_ftp(
        self, coll_id: int, folder_name: str, *, delete_source: bool = True
    ) -> int:
        """Ingest a previously FTP-uploaded folder as a document; return jobId."""
        resp = self._request(
            "POST",
            f"/collections/{coll_id}/ingest",
            params={
                "fileName": folder_name,
                "doDeleteImportSource": str(delete_source).lower(),
            },
        )
        return self._parse_job_id(resp)

    # -- layout analysis --------------------------------------------------
    def _page_selectors(self, coll_id: int, doc_id: int) -> list[dict]:
        """Build {pageId, tsId} descriptors for every page from the fulldoc."""
        fd = self._get_json(f"/collections/{coll_id}/{doc_id}/fulldoc")
        sels: list[dict] = []
        for p in fd.get("pageList", {}).get("pages", []):
            ts = p.get("tsList", {}).get("transcripts", [])
            sel = {"pageId": p["pageId"]}
            if ts:
                sel["tsId"] = ts[0]["tsId"]
            sels.append(sel)
        return sels

    def run_layout_analysis(
        self, coll_id: int, doc_id: int, *, do_line_seg: bool = True, do_block_seg: bool = True
    ) -> int:
        """Run baseline/line detection on all pages of a document; return jobId.

        PyLaia HTR needs existing line polygons, so this must run before run_htr on
        freshly uploaded documents.
        """
        body = [{"docId": doc_id, "pageList": {"pages": self._page_selectors(coll_id, doc_id)}}]
        params = {
            "collId": coll_id,
            "doLineSeg": str(do_line_seg).lower(),
            "doBlockSeg": str(do_block_seg).lower(),
            "doBaselineToPolygon": "true",
        }
        data = self._as_json(self._request("POST", "/LA/analyze", params=params, json=body))
        if isinstance(data, list) and data:
            return int(data[0]["jobId"])
        raise TranskribusError(f"Unexpected LA response: {str(data)[:200]}")

    # -- recognition ------------------------------------------------------
    _PROVIDER_ENGINE = {
        "PyLaia": "pylaia",
        "TrHtr": "trhtr",
        "CITlabPlus": "citlab",
        "CITlab": "citlab",
    }

    def resolve_engine(self, coll_id: int, model_id: int) -> str:
        """Pick the recognition engine from the model's provider."""
        for m in self.list_models(coll_id):
            if m.model_id == model_id:
                engine = self._PROVIDER_ENGINE.get(m.provider)
                if not engine:
                    raise TranskribusError(
                        f"Unknown provider {m.provider!r} for model {model_id}"
                    )
                return engine
        raise TranskribusError(f"Model {model_id} not available in collection {coll_id}")

    def run_htr(
        self,
        coll_id: int,
        doc_id: int,
        model_id: int,
        *,
        engine: str = "auto",
        pages: str | None = None,
    ) -> int:
        """Submit an HTR job and return its jobId.

        ``engine`` defaults to "auto" — resolved from the model's provider
        (PyLaia / TrHtr / CITlab). The Text Titan super models are TrHtr; the
        Kurrent / Czech M-series are PyLaia.
        """
        if engine == "auto":
            engine = self.resolve_engine(coll_id, model_id)
        if engine == "pylaia":
            path = f"/pylaia/{coll_id}/{model_id}/recognition"
        elif engine == "trhtr":
            path = f"/recognition/{coll_id}/{model_id}/trhtr"
        elif engine == "citlab":
            path = f"/recognition/{coll_id}/{model_id}/htrCITlab"
        else:
            raise ValueError(f"Unknown HTR engine: {engine!r}")
        params: dict[str, object] = {"id": doc_id}
        if pages:
            params["pages"] = pages
        resp = self._request("POST", path, params=params)
        return self._parse_job_id(resp)

    # -- jobs -------------------------------------------------------------
    def get_job(self, job_id: int) -> Job:
        data = self._get_json(f"/jobs/{job_id}")
        state = (data.get("state") or "").upper()
        try:
            status = JobStatus(state)
        except ValueError:
            status = JobStatus.UNKNOWN
        return Job(job_id=job_id, status=status, description=data.get("description", ""))

    def wait_for_job(self, job_id: int, *, poll: float = 10.0, timeout: float = 7200.0) -> Job:
        deadline = time.monotonic() + timeout
        while True:
            job = self.get_job(job_id)
            if job.status.is_terminal:
                if not job.status.is_success:
                    raise TranskribusError(f"Job {job_id} ended as {job.status.value}")
                return job
            if time.monotonic() > deadline:
                raise TranskribusError(f"Job {job_id} not finished within {timeout}s")
            time.sleep(poll)

    # -- transcripts ------------------------------------------------------
    def get_page_xml(self, coll_id: int, doc_id: int, page_nr: int) -> str:
        """Fetch the current transcript of a page as PAGE XML."""
        meta = self._get_json(f"/collections/{coll_id}/{doc_id}/{page_nr}/curr")
        url = meta.get("url") or meta.get("xmlUrl")
        if not url:
            raise TranskribusError(f"No transcript URL for page {page_nr} (doc {doc_id})")
        resp = self._request("GET", url, headers={"Accept": "application/xml"})
        resp.raise_for_status()
        return resp.text

    # -- helpers ----------------------------------------------------------
    def _get_json(self, path: str, *, params: dict | None = None):
        return self._as_json(self._request("GET", path, params=params or {}))

    def _as_json(self, resp: httpx.Response):
        if resp.status_code >= 400:
            raise TranskribusError(
                f"{resp.request.method} {resp.url} -> {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    def _parse_job_id(self, resp: httpx.Response) -> int:
        if resp.status_code >= 400:
            raise TranskribusError(f"HTR submit failed ({resp.status_code}): {resp.text[:300]}")
        text = resp.text.strip().strip('"')
        if text.isdigit():
            return int(text)
        try:
            data = resp.json()
        except ValueError as exc:
            raise TranskribusError(f"Could not parse jobId: {text[:200]}") from exc
        for key in ("jobId", "id"):
            if key in data:
                return int(data[key])
        raise TranskribusError(f"No jobId in response: {text[:200]}")
