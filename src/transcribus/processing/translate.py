# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Pluggable translation step.

Translation is intentionally a no-op for now (per project scope: transcribe
first, translate later). The ``Translator`` protocol lets a future
``ClaudeTranslator`` / ``DeepLTranslator`` slot in without touching the
pipeline.
"""

from __future__ import annotations

from typing import Protocol


class Translator(Protocol):
    def translate(self, text: str, *, source_lang: str = "", target_lang: str = "cs") -> str:
        ...


class NoopTranslator:
    """Identity translator — returns the input unchanged."""

    def translate(self, text: str, *, source_lang: str = "", target_lang: str = "cs") -> str:
        return text


def get_translator(name: str = "noop") -> Translator:
    if name == "noop":
        return NoopTranslator()
    # Future: "claude", "deepl"
    raise ValueError(f"Unknown translator: {name!r}")
