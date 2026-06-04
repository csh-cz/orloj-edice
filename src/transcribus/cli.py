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


def _parse_pages(spec: str) -> list[int]:
    """Parse a page spec like '3,50,55-61' into a sorted list of ints."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        elif part:
            out.add(int(part))
    return sorted(out)


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
    engine: str = typer.Option("auto", "--engine", help="pylaia | citlab"),
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
def tables(
    out: Path = typer.Option(..., "--out", help="Work directory (uses its scans/)"),
    pages: str = typer.Option(..., "--pages", help="Table pages, e.g. '3,50,55-61,66'"),
) -> None:
    """Extract table structure from table-page scans via Docling (TableFormer)."""
    from transcribus.processing.docling_tables import (
        docling_available,
        extract_tables,
        tables_to_json,
    )

    if not docling_available():
        raise typer.BadParameter("Docling CLI not found on PATH.")
    scans = Path(out) / "scans"
    tdir = Path(out) / "tables"
    tdir.mkdir(parents=True, exist_ok=True)
    for n in _parse_pages(pages):
        img = scans / f"{n:04d}.jpg"
        if not img.exists():
            typer.echo(f"f{n:04d}: scan missing, skip")
            continue
        tbls = extract_tables(img)
        (tdir / f"{n:04d}.json").write_text(tables_to_json(tbls), encoding="utf-8")
        cells = sum(len(t.cells) for t in tbls)
        typer.echo(f"f{n:04d}: {len(tbls)} tables, {cells} cells")


@app.command()
def figures(
    out: Path = typer.Option(..., "--out", help="Work directory (uses its scans/)"),
    pages: str = typer.Option(..., "--pages", help="Folios with figures, e.g. '71,73'"),
) -> None:
    """Crop figures from named folios via Docling (targeted, for real diagrams)."""
    import json

    from transcribus.processing.docling_tables import (
        crop_figures,
        docling_available,
        extract_layout,
    )

    if not docling_available():
        raise typer.BadParameter("Docling CLI not found on PATH.")
    out = Path(out)
    scans = out / "scans"
    figs_dir = out / "figures"
    for n in _parse_pages(pages):
        img = scans / f"{n:04d}.jpg"
        if not img.exists():
            typer.echo(f"f{n:04d}: scan missing, skip")
            continue
        _tables, boxes = extract_layout(img)
        names = crop_figures(img, boxes, figs_dir, n)
        if names:
            figs_dir.mkdir(parents=True, exist_ok=True)
            (figs_dir / f"{n:04d}.json").write_text(
                json.dumps(names, ensure_ascii=False), encoding="utf-8"
            )
        typer.echo(f"f{n:04d}: {len(names)} figure(s) cropped {names}")


@app.command()
def layout(
    out: Path = typer.Option(..., "--out", help="Work directory (uses its scans/)"),
) -> None:
    """Full Docling layout over ALL scans: tables + figures (cropped locally)."""
    import json
    import tempfile

    from PIL import Image

    from transcribus.processing.docling_tables import (
        _tables_from_doc,
        crop_figures,
        docling_available,
        pictures_px_from_doc,
        run_docling_dir,
        tables_to_json,
    )

    if not docling_available():
        raise typer.BadParameter("Docling CLI not found on PATH.")
    out = Path(out)
    scans = out / "scans"
    n_tables = n_figs = 0
    with tempfile.TemporaryDirectory() as td:
        typer.echo("Running Docling over all scans (single model load)…")
        run_docling_dir(scans, Path(td))
        for jf in sorted(Path(td).glob("*.json")):
            try:
                n = int(jf.stem)
            except ValueError:
                continue
            doc = json.loads(jf.read_text(encoding="utf-8"))
            tabs = _tables_from_doc(doc)
            if tabs:
                (out / "tables").mkdir(parents=True, exist_ok=True)
                (out / "tables" / f"{n:04d}.json").write_text(
                    tables_to_json(tabs), encoding="utf-8"
                )
                n_tables += 1
            scan = scans / f"{n:04d}.jpg"
            if scan.exists():
                with Image.open(scan) as im:
                    w, h = im.size
                names = crop_figures(scan, pictures_px_from_doc(doc, w, h), out / "figures", n)
                if names:
                    (out / "figures").mkdir(parents=True, exist_ok=True)
                    (out / "figures" / f"{n:04d}.json").write_text(
                        json.dumps(names, ensure_ascii=False), encoding="utf-8"
                    )
                    n_figs += 1
                    typer.echo(f"f{n:04d}: {len(names)} figure(s)")
    typer.echo(f"Done: {n_tables} pages with tables, {n_figs} pages with figures.")


@app.command()
def edition(
    out: Path = typer.Option(..., "--out", help="Work directory (uses its page_xml/)"),
    title: str = typer.Option("Edice", "--title"),
    ahmp_permalink: str | None = typer.Option(None, "--ahmp-permalink", help="AHMP viewer link"),
    teige: Path | None = typer.Option(None, "--teige", help="Teige reference text for collation"),
    embed_scan: bool = typer.Option(
        False, "--embed-scan/--no-embed-scan",
        help="Embed per-folio AHMP viewer in a collapsible iframe (preview; not republication)",
    ),
) -> None:
    """Generate a static HTML edition (diplomatic/normalized/Teige modes) from PAGE XML."""
    from transcribus.processing.edition import build_edition

    if teige is None:
        default = Path("data/teige_taborsky.txt")
        teige = default if default.exists() else None
    result = build_edition(
        Path(out), title=title, ahmp_permalink=ahmp_permalink, teige_path=teige,
        embed_scan=embed_scan,
    )
    typer.echo(f"Edition: {result}")


@app.command()
def htr(
    out: Path = typer.Option(..., "--out", help="Work directory (gets page_xml/ + text/)"),
    coll_id: int = typer.Option(..., "--coll", help="Collection ID"),
    doc_id: int = typer.Option(..., "--doc", help="Existing document ID to recognize"),
    model_id: int = typer.Option(..., "--model-id", help="HTR model id"),
    engine: str = typer.Option("auto", "--engine", help="pylaia | citlab"),
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
