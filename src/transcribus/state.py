# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Persistent per-job state for a resumable pipeline.

Each pipeline run owns a work directory containing ``state.json``. Phases read
the state to decide what is already done and write back their results, so an
interrupted run can be resumed idempotently.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
from pathlib import Path


class Phase(StrEnum):
    NEW = "new"
    ACQUIRED = "acquired"  # scans downloaded locally
    UPLOADED = "uploaded"  # document created on Transkribus
    RECOGNIZED = "recognized"  # HTR job submitted + finished
    EXPORTED = "exported"  # PAGE XML fetched
    CLEANED = "cleaned"  # text assembled / normalized
    TRANSLATED = "translated"  # optional final step

    @property
    def rank(self) -> int:
        order = list(Phase)
        return order.index(self)


@dataclass
class JobState:
    """Mutable state of a single pipeline run, persisted to ``state.json``."""

    source: str = ""
    ref: str = ""
    phase: Phase = Phase.NEW

    # Acquisition
    scan_count: int = 0

    # Transkribus
    coll_id: int | None = None
    doc_id: int | None = None
    model_id: int | None = None
    job_id: int | None = None

    # Free-form notes / diagnostics
    notes: dict[str, str] = field(default_factory=dict)

    # --- persistence -----------------------------------------------------
    @staticmethod
    def _path(work_dir: Path) -> Path:
        return Path(work_dir) / "state.json"

    @classmethod
    def load(cls, work_dir: Path) -> JobState:
        path = cls._path(work_dir)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["phase"] = Phase(data.get("phase", Phase.NEW.value))
        # Ignore unknown / legacy fields so old state.json files stay loadable.
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, work_dir: Path) -> None:
        path = self._path(work_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data["phase"] = self.phase.value
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def reached(self, phase: Phase) -> bool:
        """True if the run has already completed (at least) ``phase``."""
        return self.phase.rank >= phase.rank

    def advance(self, phase: Phase, work_dir: Path) -> None:
        """Mark ``phase`` as done if not already past it, then persist."""
        if phase.rank > self.phase.rank:
            self.phase = phase
        self.save(work_dir)
