"""Sotlas Flight Diagnostics & Redress Engine.

Structured diagnostics and surgical source code corrections (Redress)
for the compiler, linter, and Sotlas Studio environment.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SourceSpan:
    """Precise source code region delimited by lines, columns, and byte offsets."""
    file: str
    start_line: int
    start_col: int
    start_offset: int
    end_line: int
    end_col: int
    end_offset: int

    def __str__(self) -> str:
        return f"{self.file}:{self.start_line}:{self.start_col}"


@dataclass
class Redress:
    """Surgical code modification proposed by diagnostics."""
    span: SourceSpan
    replacement: str
    description: str

    def __str__(self) -> str:
        return f"redress [{self.span}]: '{self.replacement}' ({self.description})"


@dataclass
class FlightDiagnostic:
    """Diagnostic emitted during in-flight compilation or lint analysis."""
    code: str
    severity: str  # "error", "warning", "note"
    message: str
    span: SourceSpan
    redresses: List[Redress] = field(default_factory=list)

    def format(self) -> str:
        base = f"{self.span}: {self.severity}: [{self.code}] {self.message}"
        if self.redresses:
            sub = [f"    --> suggested redress: {r.description} -> '{r.replacement}'" for r in self.redresses]
            return base + "\n" + "\n".join(sub)
        return base


def apply_redresses(source: str, redresses: List[Redress]) -> str:
    """Applies surgical redresses to source text in reverse byte offset order."""
    if not redresses:
        return source

    ordered = sorted(redresses, key=lambda r: r.span.start_offset, reverse=True)
    result = source
    for r in ordered:
        start = r.span.start_offset
        end = r.span.end_offset
        if 0 <= start <= end <= len(result):
            result = result[:start] + r.replacement + result[end:]
    return result
