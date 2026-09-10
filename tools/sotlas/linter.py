"""Sotlas Linter (sotlas lint) & Flight Diagnostics Engine.

Analyzes Sotlas source code and emits structured diagnostics with surgical
redress suggestions (Redress) for idioms, code hygiene, and safety.
"""
from __future__ import annotations
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional

from .diagnostics import SourceSpan, Redress, FlightDiagnostic, apply_redresses


@dataclass
class LintWarning:
    file: str
    line: int
    column: int
    rule: str
    message: str
    severity: str = "warning"  # "warning" or "info"
    diagnostic: Optional[FlightDiagnostic] = None

    def format(self) -> str:
        return f"{self.file}:{self.line}:{self.column}: {self.severity}: [{self.rule}] {self.message}"


def _to_snake_case(name: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def lint_source_diagnostics(source: str, filename: str = "<input>") -> List[FlightDiagnostic]:
    """Performs static lint analysis returning structured flight diagnostics with redresses."""
    diagnostics: List[FlightDiagnostic] = []

    lines = source.splitlines(keepends=True)
    line_offsets = []
    curr_off = 0
    for l in lines:
        line_offsets.append(curr_off)
        curr_off += len(l)

    for idx, raw_line in enumerate(lines, start=1):
        line_offset = line_offsets[idx - 1]
        stripped = raw_line.strip()

        # 1. Line length check
        line_no_nl = raw_line.rstrip("\r\n")
        if len(line_no_nl) > 120 and not stripped.startswith("//"):
            span = SourceSpan(
                file=filename,
                start_line=idx,
                start_col=121,
                start_offset=line_offset + 120,
                end_line=idx,
                end_col=len(line_no_nl) + 1,
                end_offset=line_offset + len(line_no_nl)
            )
            diagnostics.append(FlightDiagnostic(
                code="line-length",
                severity="warning",
                message=f"Line with {len(line_no_nl)} characters exceeds recommended limit of 120",
                span=span
            ))

        # 2. Function naming convention: snake_case
        fn_match = re.search(r"\bfn\s+([A-Z][a-zA-Z0-9_]*)\s*\(", raw_line)
        if fn_match:
            fn_name = fn_match.group(1)
            col = raw_line.find(fn_name) + 1
            start_off = line_offset + raw_line.find(fn_name)
            end_off = start_off + len(fn_name)
            suggested = _to_snake_case(fn_name)
            span = SourceSpan(
                file=filename,
                start_line=idx,
                start_col=col,
                start_offset=start_off,
                end_line=idx,
                end_col=col + len(fn_name),
                end_offset=end_off
            )
            redress = Redress(
                span=span,
                replacement=suggested,
                description=f"convert function name to snake_case '{suggested}'"
            )
            diagnostics.append(FlightDiagnostic(
                code="naming-fn-snake-case",
                severity="warning",
                message=f"Function '{fn_name}' should use snake_case (e.g. '{suggested}')",
                span=span,
                redresses=[redress]
            ))

        # 3. Type naming convention: PascalCase
        type_match = re.search(r"\b(struct|class)\s+([a-z][a-zA-Z0-9_]*)\b", raw_line)
        if type_match:
            kind = type_match.group(1)
            type_name = type_match.group(2)
            col = raw_line.find(type_name) + 1
            start_off = line_offset + raw_line.find(type_name)
            end_off = start_off + len(type_name)
            suggested = type_name[0].upper() + type_name[1:]
            span = SourceSpan(
                file=filename,
                start_line=idx,
                start_col=col,
                start_offset=start_off,
                end_line=idx,
                end_col=col + len(type_name),
                end_offset=end_off
            )
            redress = Redress(
                span=span,
                replacement=suggested,
                description=f"convert type name to PascalCase '{suggested}'"
            )
            diagnostics.append(FlightDiagnostic(
                code="naming-type-pascal-case",
                severity="warning",
                message=f"{kind.capitalize()} '{type_name}' should use PascalCase (e.g. '{suggested}')",
                span=span,
                redresses=[redress]
            ))

        # 4. Tabulation check
        if "\t" in raw_line and not (stripped.startswith("//") or stripped.startswith("/*")):
            for tab_idx in [i for i, ch in enumerate(raw_line) if ch == "\t"]:
                col = tab_idx + 1
                start_off = line_offset + tab_idx
                end_off = start_off + 1
                span = SourceSpan(
                    file=filename,
                    start_line=idx,
                    start_col=col,
                    start_offset=start_off,
                    end_line=idx,
                    end_col=col + 1,
                    end_offset=end_off
                )
                redress = Redress(
                    span=span,
                    replacement="    ",
                    description="replace tab with 4 spaces"
                )
                diagnostics.append(FlightDiagnostic(
                    code="no-tabs",
                    severity="warning",
                    message="Use spaces instead of tabs (standard indentation: 4 spaces)",
                    span=span,
                    redresses=[redress]
                ))

    return diagnostics


def lint_source(source: str, filename: str = "<input>") -> List[LintWarning]:
    """Runs static lint checks on Sotlas source (backward compatibility)."""
    diagnostics = lint_source_diagnostics(source, filename)
    warnings: List[LintWarning] = []
    for d in diagnostics:
        warnings.append(LintWarning(
            file=d.span.file,
            line=d.span.start_line,
            column=d.span.start_col,
            rule=d.code,
            message=d.message,
            severity=d.severity,
            diagnostic=d
        ))
    return warnings


def lint_and_fix_source(source: str, filename: str = "<input>") -> Tuple[str, List[FlightDiagnostic]]:
    """Analyzes source and automatically applies all suggested redresses."""
    diagnostics = lint_source_diagnostics(source, filename)
    all_redresses = []
    for d in diagnostics:
        all_redresses.extend(d.redresses)
    fixed_text = apply_redresses(source, all_redresses)
    return fixed_text, diagnostics


def lint_file(file_path: Path, autofix: bool = False) -> int:
    """Runs linter on a .sotlas file and optionally applies redresses."""
    text = file_path.read_text(encoding="utf-8")
    if autofix:
        fixed_text, diagnostics = lint_and_fix_source(text, filename=str(file_path))
        if fixed_text != text:
            file_path.write_text(fixed_text, encoding="utf-8")
            print(f"sotlas lint: redresses successfully applied to {file_path}")
        warnings = lint_source(fixed_text, filename=str(file_path))
    else:
        warnings = lint_source(text, filename=str(file_path))

    for w in warnings:
        print(w.format())
    if warnings:
        print(f"sotlas lint: {len(warnings)} warnings found in {file_path}")
        return 1
    print(f"sotlas lint: ok — {file_path}")
    return 0
