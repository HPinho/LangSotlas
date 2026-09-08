"""Sotlas Documentation Generator (sotlas doc).

Extrai comentários de documentação '///' e gera documentação estruturada
em Markdown e HTML para módulos Sotlas.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class DocItem:
    kind: str # "module", "function", "struct", "class", "enum"
    name: str
    signature: str
    docstring: str
    line: int


def extract_docs(source: str) -> List[DocItem]:
    """Extrai itens documentados com '///' no código fonte."""
    items: List[DocItem] = []
    lines = source.splitlines()

    pending_docs: List[str] = []
    for idx, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if stripped.startswith("///"):
            doc_text = stripped[3:].strip()
            pending_docs.append(doc_text)
            continue

        if not stripped:
            continue

        # Declaração de módulo
        mod_match = re.match(r"^module\s+([a-zA-Z0-9_:]+);", stripped)
        if mod_match:
            doc = "\n".join(pending_docs)
            items.append(DocItem(
                kind="module",
                name=mod_match.group(1),
                signature=stripped,
                docstring=doc,
                line=idx
            ))
            pending_docs = []
            continue

        # Funções públicas
        fn_match = re.match(r"^(?:@system\s+)?(?:pub\s+)?fn\s+([a-zA-Z0-9_]+)\s*\((.*?)\)(?:\s*->\s*([^{;]+))?", stripped)
        if fn_match:
            doc = "\n".join(pending_docs)
            fn_name = fn_match.group(1)
            items.append(DocItem(
                kind="function",
                name=fn_name,
                signature=stripped.rstrip("{").strip(),
                docstring=doc,
                line=idx
            ))
            pending_docs = []
            continue

        # Structs públicas
        struct_match = re.match(r"^(?:pub\s+)?struct\s+([a-zA-Z0-9_]+)", stripped)
        if struct_match:
            doc = "\n".join(pending_docs)
            items.append(DocItem(
                kind="struct",
                name=struct_match.group(1),
                signature=stripped.rstrip("{").strip(),
                docstring=doc,
                line=idx
            ))
            pending_docs = []
            continue

        # Classes públicas
        class_match = re.match(r"^(?:pub\s+)?class\s+([a-zA-Z0-9_]+)", stripped)
        if class_match:
            doc = "\n".join(pending_docs)
            items.append(DocItem(
                kind="class",
                name=class_match.group(1),
                signature=stripped.rstrip("{").strip(),
                docstring=doc,
                line=idx
            ))
            pending_docs = []
            continue

        # Enums públicos
        enum_match = re.match(r"^(?:pub\s+)?enum\s+([a-zA-Z0-9_]+)", stripped)
        if enum_match:
            doc = "\n".join(pending_docs)
            items.append(DocItem(
                kind="enum",
                name=enum_match.group(1),
                signature=stripped.rstrip("{").strip(),
                docstring=doc,
                line=idx
            ))
            pending_docs = []
            continue

        # Se encontrou outra linha sem item correspondente, limpa pending_docs
        pending_docs = []

    return items


def generate_markdown(items: List[DocItem], title: str = "Documentação da API Sotlas") -> str:
    """Renderiza a lista de DocItem em formato Markdown elegante."""
    out: List[str] = [f"# {title}\n"]

    modules = [i for i in items if i.kind == "module"]
    if modules:
        for m in modules:
            out.append(f"## Módulo `{m.name}`\n")
            if m.docstring:
                out.append(f"{m.docstring}\n")

    types = [i for i in items if i.kind in ("struct", "class", "enum")]
    if types:
        out.append("## Tipos e Estruturas\n")
        for t in types:
            out.append(f"### `{t.name}` ({t.kind})\n")
            out.append(f"```sotlas\n{t.signature}\n```\n")
            if t.docstring:
                out.append(f"{t.docstring}\n")

    functions = [i for i in items if i.kind == "function"]
    if functions:
        out.append("## Funções\n")
        for f in functions:
            out.append(f"### `fn {f.name}`\n")
            out.append(f"```sotlas\n{f.signature}\n```\n")
            if f.docstring:
                out.append(f"{f.docstring}\n")

    return "\n".join(out)


def docgen_file(file_path: Path, output_file: Optional[Path] = None) -> int:
    """Gera documentação Markdown a partir de um arquivo .sotlas."""
    text = file_path.read_text(encoding="utf-8")
    items = extract_docs(text)
    md = generate_markdown(items, title=f"Documentação: {file_path.stem}")

    out_path = output_file or file_path.with_suffix(".md")
    out_path.write_text(md, encoding="utf-8")
    print(f"sotlas doc: documentação gerada em {out_path} ({len(items)} itens documentados)")
    return 0
