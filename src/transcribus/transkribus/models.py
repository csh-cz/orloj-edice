# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Value objects for the Transkribus TrpServer API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class JobStatus(StrEnum):
    CREATED = "CREATED"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    UNKNOWN = "UNKNOWN"

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.FINISHED, JobStatus.FAILED, JobStatus.CANCELED)

    @property
    def is_success(self) -> bool:
        return self is JobStatus.FINISHED


@dataclass
class Collection:
    coll_id: int
    name: str


@dataclass
class Document:
    doc_id: int
    title: str
    n_pages: int = 0


@dataclass
class HtrModel:
    model_id: int
    name: str
    model_type: str = ""  # e.g. "text" (PyLaia) or "htr" (CITlab)
    language: str = ""
    provider: str = ""


@dataclass
class Job:
    job_id: int
    status: JobStatus
    description: str = ""
