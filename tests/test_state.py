# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
import json

from transcribus.state import JobState, Phase


def test_load_ignores_legacy_fields(tmp_path):
    # A state.json from an older schema (Metagrapho era) with unknown fields.
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "source": "ahmp",
                "ref": "xid",
                "phase": "acquired",
                "scan_count": 81,
                "htr_id": 999,  # legacy / unknown
                "processes": {"1": 5},  # legacy / unknown
            }
        ),
        encoding="utf-8",
    )
    st = JobState.load(tmp_path)
    assert st.scan_count == 81
    assert st.phase is Phase.ACQUIRED


def test_advance_and_roundtrip(tmp_path):
    st = JobState(source="ahmp", ref="x")
    st.advance(Phase.ACQUIRED, tmp_path)
    again = JobState.load(tmp_path)
    assert again.reached(Phase.ACQUIRED)
    assert not again.reached(Phase.RECOGNIZED)
