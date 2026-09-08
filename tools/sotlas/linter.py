"""Sotlas Linter (sotlas lint).

Analisa arquivos de código Sotlas e emite avisos de estilo, boas práticas
e armadilhas de segurança de sistemas.
"""
from __future__ import annotations
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class LintWarning:
    file: str
    line: int
    column: int
    rule: str
    message: str
    severity: str = "warning" # "warning" ou "info"

    def format(self) -> str:
        return f"{self.file}:{self.line}:{self.column}: {self.severity}: [{self.rule}] {self.message}"


def lint_source(source: str, filename: str = "<input>") -> List[LintWarning]:
    """Executa regras estáticas de lint no código fonte Sotlas."""
    warnings: List[LintWarning] = []
    lines = source.splitlines()

    for idx, raw_line in enumerate(lines, start=1):
        # 1. Comprimento de linha excessivo
        if len(raw_line) > 120 and not raw_line.strip().startswith("//"):
            warnings.append(LintWarning(
                file=filename,
                line=idx,
                column=121,
                rule="line-length",
                message=f"Linha com {len(raw_line)} caracteres excede o limite recomendado de 120"
            ))

        stripped = raw_line.strip()

        # 2. Convenção de nomes: funções devem ser snake_case
        fn_match = re.search(r"\bfn\s+([A-Z][a-zA-Z0-9_]*)\s*\(", stripped)
        if fn_match:
            fn_name = fn_match.group(1)
            warnings.append(LintWarning(
                file=filename,
                line=idx,
                column=raw_line.find(fn_name) + 1,
                rule="naming-fn-snake-case",
                message=f"Função '{fn_name}' deve usar snake_case (exemplo: '{fn_name.lower()}')"
            ))

        # 3. Convenção de nomes: Structs e Classes devem ser PascalCase
        type_match = re.search(r"\b(struct|class)\s+([a-z][a-zA-Z0-9_]*)\b", stripped)
        if type_match:
            kind = type_match.group(1)
            type_name = type_match.group(2)
            pascal_hint = type_name.capitalize()
            warnings.append(LintWarning(
                file=filename,
                line=idx,
                column=raw_line.find(type_name) + 1,
                rule="naming-type-pascal-case",
                message=f"{kind.capitalize()} '{type_name}' deve usar PascalCase (exemplo: '{pascal_hint}')"
            ))

        # 4. Checagem de tabulações em vez de espaços
        if "\t" in raw_line and not (stripped.startswith("//") or stripped.startswith("/*")):
            warnings.append(LintWarning(
                file=filename,
                line=idx,
                column=raw_line.find("\t") + 1,
                rule="no-tabs",
                message="Use espaços em vez de tabulações (indentação padrão: 4 espaços)"
            ))

    return warnings


def lint_file(file_path: Path) -> int:
    """Executa o linter em um arquivo .sotlas e imprime os avisos encontrados."""
    text = file_path.read_text(encoding="utf-8")
    warnings = lint_source(text, filename=str(file_path))
    for w in warnings:
        print(w.format())
    if warnings:
        print(f"sotlas lint: {len(warnings)} avisos encontrados em {file_path}")
        return 1
    print(f"sotlas lint: ok — {file_path}")
    return 0
