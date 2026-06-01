# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Transkribus TrpServer API client."""

from transcribus.transkribus.client import DEFAULT_BASE_URL, TranskribusClient, TranskribusError
from transcribus.transkribus.models import Collection, Document, HtrModel, Job, JobStatus

__all__ = [
    "TranskribusClient",
    "TranskribusError",
    "DEFAULT_BASE_URL",
    "Collection",
    "Document",
    "HtrModel",
    "Job",
    "JobStatus",
]
