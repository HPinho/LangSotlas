#!/usr/bin/env python3
"""Script utilitário para gerar o pacote de código-fonte e o Hash SHA-512 para registro no INPI."""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "dist" / "inpi"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ZIP_PATH = OUT_DIR / "sotlas-source-inpi-v0.3.0.zip"

INCLUDE_DIRS = [
    "compiler", "tools", "bootstrap", "stdlib",
    "editors", "packaging", "tests", "examples", "web", "docs"
]
INCLUDE_FILES = ["setup.py", "pyproject.toml", "LICENSE", "README.md"]


def main():
    print("Gerando pacote limpo do código-fonte para o INPI...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        for f in INCLUDE_FILES:
            fp = ROOT / f
            if fp.exists():
                z.write(fp, arcname=f)
        for d in INCLUDE_DIRS:
            dp = ROOT / d
            if dp.exists():
                for p in sorted(dp.rglob("*")):
                    if p.is_file():
                        if "__pycache__" in p.parts or p.suffix in (".pyc", ".obj", ".o", ".exe", ".tmp"):
                            continue
                        arcname = p.relative_to(ROOT)
                        z.write(p, arcname=str(arcname))

    content = ZIP_PATH.read_bytes()
    sha512 = hashlib.sha512(content).hexdigest()
    sha256 = hashlib.sha256(content).hexdigest()

    print(f"\n[OK] Pacote gerado com sucesso em:")
    print(f"     {ZIP_PATH} ({len(content) / 1024:.2f} KB)")
    print(f"\n[HASH OFICIAL INPI - SHA-512]:")
    print(f"{sha512}")
    print(f"\n[HASH ALTERNATIVO - SHA-256]:")
    print(f"{sha256}\n")


if __name__ == "__main__":
    main()
