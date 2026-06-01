# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""End-to-end pipeline orchestration (TrpServer).

Each phase is idempotent and gated by the persisted :class:`JobState`, so a run
can be interrupted and resumed. Phases:

    acquire -> upload -> recognize -> wait -> export -> clean -> [translate]
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from transcribus.config import Settings
from transcribus.processing.cleanup import assemble_markdown
from transcribus.processing.page_xml import page_to_lines
from transcribus.sources import SOURCES
from transcribus.state import JobState, Phase
from transcribus.transkribus import TranskribusClient, TranskribusError


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        work_dir: Path,
        *,
        source: str,
        ref: str,
        coll_id: int | None,
        model_id: int | None,
        engine: str = "pylaia",
        limit: int | None = None,
    ) -> None:
        self.settings = settings
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.state = JobState.load(self.work_dir)
        self.state.source = source
        self.state.ref = ref
        if coll_id is not None:
            self.state.coll_id = coll_id
        if model_id is not None:
            self.state.model_id = model_id
        self.engine = engine
        self.limit = limit
        self._client: TranskribusClient | None = None

    def client(self) -> TranskribusClient:
        if self._client is None:
            self.settings.require_credentials()
            self._client = TranskribusClient(self.settings.base_url)
            self._client.login(self.settings.user, self.settings.password)
        return self._client

    @property
    def scans_dir(self) -> Path:
        return self.work_dir / "scans"

    @property
    def xml_dir(self) -> Path:
        return self.work_dir / "page_xml"

    @property
    def text_dir(self) -> Path:
        return self.work_dir / "text"

    # -- phases -----------------------------------------------------------
    def acquire(self) -> None:
        if self.state.reached(Phase.ACQUIRED):
            return
        source_cls = SOURCES.get(self.state.source)
        if source_cls is None:
            raise ValueError(f"Unknown source: {self.state.source!r}")
        source = source_cls()
        pages = source.resolve(self.state.ref, self.scans_dir, limit=self.limit)
        manifest = [{"index": p.index, "path": p.path.name, "url": p.source_url} for p in pages]
        (self.work_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.state.scan_count = len(pages)
        self.state.advance(Phase.ACQUIRED, self.work_dir)

    def upload(self, title: str | None = None) -> None:
        if self.state.reached(Phase.UPLOADED):
            return
        if self.state.coll_id is None:
            raise ValueError("coll_id is required for upload (use --coll)")
        images = sorted(self.scans_dir.glob("*.jpg"))
        if not images:
            raise RuntimeError("No scans to upload; run acquire first")
        doc_title = title or f"{self.state.source}:{self.state.ref}"[:200]
        self.state.doc_id = self.client().create_document(
            self.state.coll_id, doc_title, images
        )
        self.state.advance(Phase.UPLOADED, self.work_dir)

    def recognize(self, *, htr_retries: int = 3) -> None:
        if self.state.reached(Phase.RECOGNIZED):
            return
        if self.state.model_id is None:
            raise ValueError("model_id is required for HTR (use --model-id)")
        client = self.client()

        # 1) Layout analysis (line detection) — PyLaia HTR needs existing line polygons.
        la_job = client.run_layout_analysis(self.state.coll_id, self.state.doc_id)
        client.wait_for_job(la_job)

        # 2) HTR. The PyLaia worker occasionally fails to create its workdir
        #    (transient server-side error); retry a few times.
        pages = f"1-{self.state.scan_count}" if self.state.scan_count else None
        last_err: Exception | None = None
        for _ in range(htr_retries):
            job_id = client.run_htr(
                self.state.coll_id,
                self.state.doc_id,
                self.state.model_id,
                engine=self.engine,
                pages=pages,
            )
            self.state.job_id = job_id
            self.state.save(self.work_dir)
            try:
                client.wait_for_job(job_id)
                break
            except TranskribusError as exc:  # noqa: PERF203
                last_err = exc
                time.sleep(10)
        else:
            raise RuntimeError(f"HTR failed after {htr_retries} attempts: {last_err}")

        self.state.advance(Phase.RECOGNIZED, self.work_dir)

    def export(self) -> None:
        if self.state.reached(Phase.EXPORTED):
            return
        self.xml_dir.mkdir(parents=True, exist_ok=True)
        client = self.client()
        for page_nr in range(1, self.state.scan_count + 1):
            xml = client.get_page_xml(self.state.coll_id, self.state.doc_id, page_nr)
            (self.xml_dir / f"{page_nr:04d}.xml").write_text(xml, encoding="utf-8")
        self.state.advance(Phase.EXPORTED, self.work_dir)

    def clean(self, title: str | None = None) -> Path:
        self.text_dir.mkdir(parents=True, exist_ok=True)
        pages: list[list[str]] = []
        for xml_file in sorted(self.xml_dir.glob("*.xml")):
            lines = page_to_lines(xml_file.read_text(encoding="utf-8"))
            pages.append(lines)
            (self.text_dir / f"{xml_file.stem}.txt").write_text(
                "\n".join(lines), encoding="utf-8"
            )
        md = assemble_markdown(pages, title=title or self.state.ref)
        out = self.text_dir / "transcript.md"
        out.write_text(md, encoding="utf-8")
        self.state.advance(Phase.CLEANED, self.work_dir)
        return out

    def run(self, *, title: str | None = None) -> Path:
        self.acquire()
        self.upload(title=title)
        self.recognize()
        self.export()
        return self.clean(title=title)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
