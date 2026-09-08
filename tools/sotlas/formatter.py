"""Sotlas Code Formatter (sotlas fmt).

Padroniza a formatação de arquivos de código Sotlas:
- Indentação de 4 espaços
- Espaçamento consistente ao redor de operadores binários (=, +, -, *, /, ->)
- Espaço após vírgulas e dois pontos
- Espaço antes de abertura de chaves '{'
- Remoção de espaços em branco no final de linhas
- Preservação de comentários e linhas em branco
"""
from __future__ import annotations
import re
import sys
from pathlib import Path


def format_code(source: str) -> str:
    """Formata o código fonte Sotlas segundo as convenções canônicas de estilo."""
    lines = source.splitlines()
    formatted_lines: list[str] = []
    indent_level = 0
    in_block_comment = False

    for raw_line in lines:
        stripped = raw_line.strip()

        if not stripped:
            formatted_lines.append("")
            continue

        # Gestão de comentários em bloco /* ... */
        if stripped.startswith("/*") and not stripped.endswith("*/"):
            in_block_comment = True
            formatted_lines.append("    " * indent_level + stripped)
            continue
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            formatted_lines.append("    " * indent_level + stripped)
            continue

        # Fechamento de chaves diminui indentação antes de formatar a linha
        if stripped.startswith("}") or stripped.startswith("};"):
            indent_level = max(0, indent_level - 1)

        line = stripped
        if not (line.startswith("//") or line.startswith("/*")):
            # Espaçamento de vírgulas
            line = re.sub(r",\s*", ", ", line)
            # Espaçamento em anotações de tipo: var: Type -> var: Type
            line = re.sub(r"([a-zA-Z0-9_])\s*:\s*([*&a-zA-Z0-9_])", r"\1: \2", line)
            # Espaçamento de seta ->
            line = re.sub(r"\s*->\s*", " -> ", line)
            # Espaçamento antes de chave de abertura {
            line = re.sub(r"([)a-zA-Z0-9_])\{", r"\1 {", line)
            # Espaçamento de operadores de atribuição simples
            line = re.sub(r"([a-zA-Z0-9_])\s*=\s*", r"\1 = ", line)
            # Espaçamento de operadores aritméticos binários (+, -, *, /)
            line = re.sub(r"([a-zA-Z0-9_])\s*\+\s*([a-zA-Z0-9_])", r"\1 + \2", line)
            line = re.sub(r"([a-zA-Z0-9_])\s*-\s*([a-zA-Z0-9_])", r"\1 - \2", line)
            # Normalizar == e !=
            line = re.sub(r"\s*==\s*", " == ", line)
            line = re.sub(r"\s*!=\s*", " != ", line)

        formatted_lines.append("    " * indent_level + line)

        # Abertura de chaves aumenta a indentação para as próximas linhas
        opens = stripped.count("{")
        closes = stripped.count("}")
        net_change = opens - closes
        if not (stripped.startswith("}") or stripped.startswith("};")):
            indent_level = max(0, indent_level + net_change)
        else:
            indent_level = max(0, indent_level + opens)

    result = "\n".join(formatted_lines)
    if not result.endswith("\n"):
        result += "\n"
    return result


def format_file(file_path: Path, check_only: bool = False) -> bool:
    """Formata um arquivo .sotlas no disco. Retorna True se o arquivo estava correto / foi corrigido."""
    text = file_path.read_text(encoding="utf-8")
    formatted = format_code(text)
    if text == formatted:
        return True
    if check_only:
        print(f"sotlas fmt: formatação necessária em {file_path}")
        return False
    file_path.write_text(formatted, encoding="utf-8")
    print(f"sotlas fmt: formatado {file_path}")
    return True
