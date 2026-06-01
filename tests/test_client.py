# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
import httpx

from transcribus.transkribus import TranskribusClient
from transcribus.transkribus.models import JobStatus


def _client(handler) -> TranskribusClient:
    http = httpx.Client(
        base_url="https://api.test/TrpServer/rest",
        transport=httpx.MockTransport(handler),
    )
    return TranskribusClient(http=http)


def test_list_collections_parses_trpserver_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"colId": 160273, "colName": "Orloj Pražský"}])

    colls = _client(handler).list_collections()
    assert colls[0].coll_id == 160273 and colls[0].name == "Orloj Pražský"


def test_run_htr_pylaia_endpoint_and_jobid():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["id"] = request.url.params.get("id")
        return httpx.Response(200, text="123456")  # job id as plain text

    job_id = _client(handler).run_htr(160273, 999, 37789, engine="pylaia")
    assert job_id == 123456
    assert captured["path"].endswith("/pylaia/160273/37789/recognition")
    assert captured["id"] == "999"


def test_ingest_from_ftp_endpoint():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["fileName"] = request.url.params.get("fileName")
        return httpx.Response(200, text="777")

    job_id = _client(handler).ingest_from_ftp(160273, "orloj1587")
    assert job_id == 777
    assert captured["path"].endswith("/collections/160273/ingest")
    assert captured["fileName"] == "orloj1587"


def test_get_job_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"state": "FINISHED"})

    job = _client(handler).get_job(123456)
    assert job.status is JobStatus.FINISHED and job.status.is_success
