"""Sotlas Package Manager — gerenciador de pacotes e projetos Sotlas.

Suporta manifestos Sotlas.toml, inicialização de pacotes (sotlas new / init),
resolução de dependências e orquestração de compilação.
"""
from __future__ import annotations
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class PackageManifest:
    name: str
    version: str = "0.1.0"
    edition: str = "2026"
    license: str = "Apache-2.0"
    authors: List[str] = field(default_factory=list)
    target_type: str = "bin" # "bin" ou "lib"
    dependencies: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_toml_text(cls, text: str) -> PackageManifest:
        """Parse simples e robusto de manifesto Sotlas.toml."""
        name = "unnamed"
        version = "0.1.0"
        edition = "2026"
        pkg_license = "Apache-2.0"
        authors: List[str] = []
        target_type = "bin"
        dependencies: Dict[str, str] = {}

        current_section = "package"
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            sec_match = re.match(r"^\[([a-zA-Z0-9_\.]+)\]$", line)
            if sec_match:
                current_section = sec_match.group(1).lower()
                continue

            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"\'')

                if current_section == "package":
                    if key == "name":
                        name = val
                    elif key == "version":
                        version = val
                    elif key == "edition":
                        edition = val
                    elif key == "license":
                        pkg_license = val
                    elif key == "target_type":
                        target_type = val
                    elif key == "authors":
                        # ex: ["Dev <dev@bakenos.org>"]
                        items = val.strip("[]").split(",")
                        authors = [it.strip().strip('"\'') for it in items if it.strip()]
                elif current_section == "dependencies":
                    dependencies[key] = val

        return cls(
            name=name,
            version=version,
            edition=edition,
            license=pkg_license,
            authors=authors,
            target_type=target_type,
            dependencies=dependencies
        )

    def to_toml_text(self) -> str:
        authors_str = ", ".join(f'"{a}"' for a in self.authors)
        deps_lines = "\n".join(f'{k} = "{v}"' for k, v in self.dependencies.items())
        return f"""[package]
name = "{self.name}"
version = "{self.version}"
edition = "{self.edition}"
license = "{self.license}"
target_type = "{self.target_type}"
authors = [{authors_str}]

[dependencies]
{deps_lines}
"""


def init_package(project_dir: Path, name: str, is_lib: bool = False) -> Path:
    """Inicializa um novo projeto Sotlas com manifesto Sotlas.toml e esqueleto de código."""
    project_dir.mkdir(parents=True, exist_ok=True)
    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)

    target_type = "lib" if is_lib else "bin"
    manifest = PackageManifest(name=name, target_type=target_type)
    toml_path = project_dir / "Sotlas.toml"
    toml_path.write_text(manifest.to_toml_text(), encoding="utf-8")

    entry_filename = "lib.sotlas" if is_lib else "main.sotlas"
    entry_path = src_dir / entry_filename

    if is_lib:
        entry_path.write_text(f"""module {name};

/// Biblioteca {name} escrita em Sotlas.
pub fn calculate(a: u32, b: u32) -> u32 {{
    return a + b;
}}
""", encoding="utf-8")
    else:
        entry_path.write_text(f"""module {name};

import core::primitives::*;

pub fn main() -> u32 {{
    return 0;
}}
""", encoding="utf-8")

    gitignore_path = project_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text("build/\ntarget/\n*.bin\n*.tmp.c\n", encoding="utf-8")

    return toml_path


def build_package(project_dir: Path, output_dir: Optional[Path] = None) -> int:
    """Compila o projeto lendo Sotlas.toml."""
    toml_path = project_dir / "Sotlas.toml"
    if not toml_path.exists():
        print(f"sotlas: erro: Sotlas.toml não encontrado em {project_dir}", file=sys.stderr)
        return 1

    manifest = PackageManifest.from_toml_text(toml_path.read_text(encoding="utf-8"))
    src_dir = project_dir / "src"
    entry_file = src_dir / ("lib.sotlas" if manifest.target_type == "lib" else "main.sotlas")

    if not entry_file.exists():
        print(f"sotlas: erro: arquivo de entrada {entry_file} não encontrado", file=sys.stderr)
        return 1

    out_dir = output_dir or (project_dir / "build")
    out_dir.mkdir(parents=True, exist_ok=True)

    from sotlas import compile_source
    text = entry_file.read_text(encoding="utf-8")
    c_code = compile_source(text, str(entry_file))

    out_c = out_dir / f"{manifest.name}.c"
    out_c.write_text(c_code, encoding="utf-8")
    print(f"sotlas: pacote '{manifest.name}' v{manifest.version} compilado -> {out_c}")
    return 0


def add_dependency(project_dir: Path, dep_name: str, dep_spec: str = "^0.1.0") -> int:
    """Adiciona uma dependência ao manifesto Sotlas.toml."""
    toml_path = project_dir / "Sotlas.toml"
    if not toml_path.exists():
        print(f"sotlas: erro: Sotlas.toml não encontrado em {project_dir}", file=sys.stderr)
        return 1

    manifest = PackageManifest.from_toml_text(toml_path.read_text(encoding="utf-8"))
    manifest.dependencies[dep_name] = dep_spec
    toml_path.write_text(manifest.to_toml_text(), encoding="utf-8")
    print(f"sotlas: adicionada dependência '{dep_name} = \"{dep_spec}\"' ao Sotlas.toml")
    return 0
