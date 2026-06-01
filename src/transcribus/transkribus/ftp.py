# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Bulk image upload to the Transkribus FTP server.

Transkribus accepts bulk uploads at ftp://transkribus.eu using the account's
login credentials. Each uploaded folder is later ingested as one document via
the REST API (POST /collections/{collId}/ingest?fileName=<folder>).

Tries plain FTP first, then explicit FTPS (FTP over TLS) as a fallback.
"""

from __future__ import annotations

import ftplib
from collections.abc import Callable, Sequence
from pathlib import Path

ProgressFn = Callable[[int, int, str], None]


def _connect(host: str, user: str, password: str, *, port: int = 21) -> ftplib.FTP:
    try:
        ftp: ftplib.FTP = ftplib.FTP()
        ftp.connect(host, port, timeout=60)
        ftp.login(user, password)
        return ftp
    except ftplib.error_perm:
        # Some deployments require TLS.
        ftp = ftplib.FTP_TLS()
        ftp.connect(host, port, timeout=60)
        ftp.login(user, password)
        ftp.prot_p()
        return ftp


def upload_folder(
    host: str,
    user: str,
    password: str,
    folder: str,
    files: Sequence[Path],
    *,
    port: int = 21,
    progress: ProgressFn | None = None,
) -> int:
    """Upload ``files`` into ``folder`` on the FTP server. Returns count uploaded."""
    ftp = _connect(host, user, password, port=port)
    try:
        try:
            ftp.mkd(folder)
        except ftplib.error_perm:
            pass  # folder already exists
        ftp.cwd(folder)
        total = len(files)
        for i, f in enumerate(files, start=1):
            with Path(f).open("rb") as fh:
                ftp.storbinary(f"STOR {Path(f).name}", fh)
            if progress:
                progress(i, total, Path(f).name)
        return total
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
