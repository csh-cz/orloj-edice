# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Command-line interface for the transcribus pipeline."""

from __future__ import annotations

from pathlib import Path

import typer

from transcribus.config import load_settings
from transcribus.pipeline import Pipeline
from transcribus.state import Phase
from transcribus.transkribus import TranskribusClient

app = typer.Typer(
    add_completion=False,
    help="Archive scans -> Transkribus HTR -> cleaned text.",
)


def _client():
    settings = load_settings()
    settings.require_credentials()
    client = TranskribusClient(settings.base_url)
    client.login(settings.user, settings.password)
    return client


@app.command()
def login(
    user: str | None = typer.Option(None, "--user", help="Override .env user/email"),
    ask_password: bool = typer.Option(
        False, "--ask-password", help="Prompt for password (hidden) instead of .env"
    ),
    otp: str | None = typer.Option(None, "--otp", help="One-time 2FA code, if enabled"),
) -> None:
    """Verify Transkribus SSO login (0 credits). Use --ask-password to paste it fresh."""
    settings = load_settings()
    u = user or settings.user
    if ask_password:
        pw = typer.prompt("Transkribus password", hide_input=True)
    else:
        pw = settings.password
    if not u or not pw:
        raise typer.BadParameter("Missing user/password (set .env or use --ask-password).")
    with TranskribusClient(settings.base_url) as client:
        client.login(u, pw, otp=otp)
        typer.echo("Login OK — SSO token acquired.")


@app.command()
def collections() -> None:
    """List Transkribus collections accessible to the account."""
    with _client() as client:
        for c in client.list_collections():
            typer.echo(f"{c.coll_id}\t{c.name}")


@app.command()
def models(coll_id: int = typer.Option(..., "--coll", help="Collection ID")) -> None:
    """List HTR models usable in a collection."""
    with _client() as client:
        for m in client.list_models(coll_id):
            typer.echo(f"{m.model_id}\t{m.model_type}\t{m.language}\t{m.name}")


@app.command()
def acquire(
    ref: str = typer.Argument(..., help="AHMP permalink URL or xid"),
    source: str = typer.Option("ahmp", "--source"),
    out: Path = typer.Option(..., "--out", help="Work directory"),
    limit: int | None = typer.Option(None, "--limit", help="Max scans to download"),
) -> None:
    """Download scans only (no Transkribus calls)."""
    settings = load_settings()
    p = Pipeline(settings, out, source=source, ref=ref, coll_id=None, model_id=None, limit=limit)
    p.acquire()
    typer.echo(f"Downloaded {p.state.scan_count} scans to {p.scans_dir}")


@app.command(name="upload-ftp")
def upload_ftp(
    out: Path = typer.Option(..., "--out", help="Work directory containing scans/"),
    coll_id: int = typer.Option(..., "--coll", help="Target collection ID"),
    folder: str | None = typer.Option(None, "--folder", help="FTP folder name (= doc title)"),
    limit: int | None = typer.Option(None, "--limit", help="Only upload first N scans (test)"),
    no_ingest: bool = typer.Option(False, "--no-ingest", help="Upload only, skip API ingest"),
) -> None:
    """Bulk-upload scans via FTP, then ingest the folder as a document (REST)."""
    from transcribus.transkribus.ftp import upload_folder

    settings = load_settings()
    settings.require_credentials()
    scans = sorted((Path(out) / "scans").glob("*.jpg"))
    if limit:
        scans = scans[:limit]
    if not scans:
        raise typer.BadParameter(f"No scans in {Path(out) / 'scans'} (run acquire first).")
    folder = folder or Path(out).name

    host, user, password = settings.ftp_credentials()
    typer.echo(f"FTP {host}: uploading {len(scans)} files to /{folder} …")

    def _progress(i: int, total: int, name: str) -> None:
        if i == total or i % 10 == 0:
            typer.echo(f"  {i}/{total} {name}")

    upload_folder(host, user, password, folder, scans, progress=_progress)
    typer.echo("Upload done.")

    if no_ingest:
        return
    with _client() as client:
        job_id = client.ingest_from_ftp(coll_id, folder)
        typer.echo(f"Ingest job {job_id}; waiting …")
        client.wait_for_job(job_id)
        doc_id = next(
            (d.doc_id for d in client.list_documents(coll_id) if d.title == folder), None
        )
        typer.echo(f"Ingested into collection {coll_id} as docId {doc_id} (title {folder!r}).")


@app.command()
def run(
    ref: str = typer.Argument(..., help="AHMP permalink URL or xid"),
    out: Path = typer.Option(..., "--out", help="Work directory"),
    source: str = typer.Option("ahmp", "--source"),
    coll_id: int | None = typer.Option(None, "--coll", help="Target collection ID"),
    model_id: int | None = typer.Option(None, "--model-id", help="HTR model id"),
    engine: str = typer.Option("pylaia", "--engine", help="pylaia | citlab"),
    limit: int | None = typer.Option(None, "--limit", help="Max scans to process"),
    title: str | None = typer.Option(None, "--title"),
) -> None:
    """Run the full pipeline: acquire -> upload -> HTR -> export -> clean."""
    settings = load_settings()
    p = Pipeline(
        settings,
        out,
        source=source,
        ref=ref,
        coll_id=coll_id if coll_id is not None else settings.coll_id,
        model_id=model_id if model_id is not None else settings.model_id,
        engine=engine,
        limit=limit,
    )
    try:
        result = p.run(title=title)
    finally:
        p.close()
    typer.echo(f"Transcript: {result}")


@app.command()
def edition(
    out: Path = typer.Option(..., "--out", help="Work directory (uses its page_xml/)"),
    title: str = typer.Option("Edice", "--title"),
    ahmp_permalink: str | None = typer.Option(None, "--ahmp-permalink", help="AHMP viewer link"),
    teige: Path | None = typer.Option(None, "--teige", help="Teige reference text for collation"),
) -> None:
    """Generate a static HTML edition (diplomatic/normalized/Teige modes) from PAGE XML."""
    from transcribus.processing.edition import build_edition

    if teige is None:
        default = Path("data/teige_taborsky.txt")
        teige = default if default.exists() else None
    result = build_edition(Path(out), title=title, ahmp_permalink=ahmp_permalink, teige_path=teige)
    typer.echo(f"Edition: {result}")


@app.command()
def htr(
    out: Path = typer.Option(..., "--out", help="Work directory (gets page_xml/ + text/)"),
    coll_id: int = typer.Option(..., "--coll", help="Collection ID"),
    doc_id: int = typer.Option(..., "--doc", help="Existing document ID to recognize"),
    model_id: int = typer.Option(..., "--model-id", help="HTR model id"),
    engine: str = typer.Option("pylaia", "--engine", help="pylaia | citlab"),
    title: str | None = typer.Option(None, "--title"),
) -> None:
    """Run HTR on an already-uploaded document: layout -> HTR -> export -> clean."""
    settings = load_settings()
    p = Pipeline(settings, out, source="ahmp", ref="", coll_id=coll_id, model_id=model_id,
                 engine=engine)
    p.state.doc_id = doc_id
    docs = {d.doc_id: d for d in p.client().list_documents(coll_id)}
    if doc_id in docs and docs[doc_id].n_pages:
        p.state.scan_count = docs[doc_id].n_pages
    if not p.state.reached(Phase.UPLOADED):
        p.state.advance(Phase.UPLOADED, p.work_dir)
    try:
        p.recognize()
        p.export()
        result = p.clean(title=title)
    finally:
        p.close()
    typer.echo(f"Transcript: {result} ({p.state.scan_count} pages)")


if __name__ == "__main__":
    app()
