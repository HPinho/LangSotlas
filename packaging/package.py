#!/usr/bin/env python3
"""
Sotlas Toolchain Release Packager.
Gera pacotes de distribuição standalone da linguagem Sotlas para Windows, Linux e macOS:
  - Arquivos portáveis compactados (.zip e .tar.gz) com SHA-256 checksums
  - Instalador automatizado PowerShell para Windows (install.ps1)
  - Instalador automatizado Shell para Linux/macOS (install.sh)
  - Script Inno Setup para instalador executável Windows (.exe)
"""
from __future__ import annotations
import argparse
import hashlib
import os
import platform
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def get_version() -> str:
    init_py = ROOT / "compiler" / "sotlas" / "__init__.py"
    if init_py.is_file():
        for line in init_py.read_text(encoding="utf-8").splitlines():
            if line.startswith("SOTLAS_VERSION"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "0.2.0"

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def create_windows_launchers(bin_dir: Path):
    # sotlas.cmd
    sotlas_cmd = bin_dir / "sotlas.cmd"
    sotlas_cmd.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"SOTLAS_HOME=%~dp0..\"\r\n"
        "set \"PYTHONPATH=%SOTLAS_HOME%\\compiler;%SOTLAS_HOME%\\tools;%PYTHONPATH%\"\r\n"
        "py -3 -m sotlas.cli %*\r\n"
        "if errorlevel 1 (\r\n"
        "    python -m sotlas.cli %*\r\n"
        ")\r\n"
        "endlocal\r\n",
        encoding="utf-8"
    )

    # sotlasc.cmd
    sotlasc_cmd = bin_dir / "sotlasc.cmd"
    sotlasc_cmd.write_text(
        "@echo off\r\n"
        "\"%~dp0sotlas.cmd\" compile %*\r\n",
        encoding="utf-8"
    )

    # sotlas-lsp.cmd
    lsp_cmd = bin_dir / "sotlas-lsp.cmd"
    lsp_cmd.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"SOTLAS_HOME=%~dp0..\"\r\n"
        "set \"PYTHONPATH=%SOTLAS_HOME%\\compiler;%SOTLAS_HOME%\\tools;%PYTHONPATH%\"\r\n"
        "py -3 -m sotlas.cli lsp %*\r\n"
        "if errorlevel 1 (\r\n"
        "    python -m sotlas.cli lsp %*\r\n"
        ")\r\n"
        "endlocal\r\n",
        encoding="utf-8"
    )

def create_unix_launchers(bin_dir: Path):
    # sotlas
    sotlas_sh = bin_dir / "sotlas"
    sotlas_sh.write_text(
        "#!/usr/bin/env bash\n"
        "DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/..\" && pwd)\"\n"
        "export SOTLAS_HOME=\"$DIR\"\n"
        "export PYTHONPATH=\"$DIR/compiler:$DIR/tools:$PYTHONPATH\"\n"
        "if command -v python3 >/dev/null 2>&1; then\n"
        "    exec python3 -m sotlas.cli \"$@\"\n"
        "else\n"
        "    exec python -m sotlas.cli \"$@\"\n"
        "fi\n",
        encoding="utf-8"
    )
    sotlas_sh.chmod(0o755)

    # sotlasc
    sotlasc_sh = bin_dir / "sotlasc"
    sotlasc_sh.write_text(
        "#!/usr/bin/env bash\n"
        "DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
        "exec \"$DIR/sotlas\" compile \"$@\"\n",
        encoding="utf-8"
    )
    sotlasc_sh.chmod(0o755)

    # sotlas-lsp
    lsp_sh = bin_dir / "sotlas-lsp"
    lsp_sh.write_text(
        "#!/usr/bin/env bash\n"
        "DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
        "exec \"$DIR/sotlas\" lsp \"$@\"\n",
        encoding="utf-8"
    )
    lsp_sh.chmod(0o755)

def assemble_bundle(bundle_dir: Path, version: str):
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)

    # 1. bin/
    bin_dir = bundle_dir / "bin"
    bin_dir.mkdir()
    create_windows_launchers(bin_dir)
    create_unix_launchers(bin_dir)

    # 2. compiler/
    comp_src = ROOT / "compiler" / "sotlas"
    comp_dst = bundle_dir / "compiler" / "sotlas"
    shutil.copytree(comp_src, comp_dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # 3. tools/
    tools_src1 = ROOT / "tools" / "sotlas"
    tools_dst1 = bundle_dir / "tools" / "sotlas"
    shutil.copytree(tools_src1, tools_dst1, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    tools_src2 = ROOT / "tools" / "sotlas_compile"
    tools_dst2 = bundle_dir / "tools" / "sotlas_compile"
    shutil.copytree(tools_src2, tools_dst2, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # 4. stdlib/
    stdlib_src = ROOT / "stdlib"
    stdlib_dst = bundle_dir / "stdlib"
    shutil.copytree(stdlib_src, stdlib_dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # 5. web/
    web_src = ROOT / "web"
    web_dst = bundle_dir / "web"
    shutil.copytree(web_src, web_dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # 6. include/
    include_dst = bundle_dir / "include"
    include_dst.mkdir()
    runtime_h = ROOT / "stdlib" / "runtime" / "runtime.h"
    if runtime_h.is_file():
        shutil.copy(runtime_h, include_dst / "runtime.h")

    # 7. assets/
    assets_src = ROOT / "assets"
    if assets_src.is_dir():
        assets_dst = bundle_dir / "assets"
        shutil.copytree(assets_src, assets_dst)

    # 8. Documentos
    for doc in ["LICENSE", "README.md", "Icone Sotlas.svg", "Logo Sotlas.svg"]:
        p = ROOT / doc
        if p.is_file():
            shutil.copy(p, bundle_dir / doc)

    # 9. Manifesto do Toolchain
    manifest = bundle_dir / "sotlas-toolchain.json"
    manifest.write_text(
        f'{{\n  "name": "sotlas",\n  "version": "{version}",\n  "release": "production",\n  "components": ["compiler", "stdlib", "studio", "repl", "wasm-backend", "lsp"]\n}}\n',
        encoding="utf-8"
    )

def main():
    parser = argparse.ArgumentParser(description="Empacotador oficial da Linguagem Sotlas")
    parser.add_argument("--version", default=get_version(), help="Versão do pacote (padrão: detectada)")
    parser.add_argument("--dist-dir", default=str(ROOT / "dist"), help="Diretório de saída para instaladores")
    parser.add_argument("--target", default="all", choices=["all", "windows", "linux", "darwin"], help="Plataforma alvo")
    args = parser.parse_args()

    version = args.version
    dist_dir = Path(args.dist_dir).resolve()
    dist_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Construindo Pacote de Distribuição Sotlas v{version} ===")

    checksums = []

    # Windows x64
    if args.target in ("all", "windows"):
        pkg_name = f"sotlas-v{version}-windows-x64"
        bundle_dir = dist_dir / pkg_name
        print(f"-> Montando bundle: {pkg_name}...")
        assemble_bundle(bundle_dir, version)

        zip_file = dist_dir / f"{pkg_name}.zip"
        print(f"-> Compactando {zip_file.name}...")
        with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_path, _, files in os.walk(bundle_dir):
                for f in files:
                    full_p = Path(root_path) / f
                    rel_p = full_p.relative_to(dist_dir)
                    zf.write(full_p, rel_p)
        
        sha = compute_sha256(zip_file)
        checksums.append(f"{sha}  {zip_file.name}")
        print(f"   SHA-256: {sha}")

    # Linux x64
    if args.target in ("all", "linux"):
        pkg_name = f"sotlas-v{version}-linux-x64"
        bundle_dir = dist_dir / pkg_name
        print(f"-> Montando bundle: {pkg_name}...")
        assemble_bundle(bundle_dir, version)

        tar_file = dist_dir / f"{pkg_name}.tar.gz"
        print(f"-> Compactando {tar_file.name}...")
        with tarfile.open(tar_file, "w:gz") as tf:
            tf.add(bundle_dir, arcname=pkg_name)
        
        sha = compute_sha256(tar_file)
        checksums.append(f"{sha}  {tar_file.name}")
        print(f"   SHA-256: {sha}")

    # Escrever SHA256SUMS.txt
    sha_file = dist_dir / "SHA256SUMS.txt"
    with open(sha_file, "w", encoding="utf-8") as f:
        f.write("\n".join(checksums) + "\n")
    print(f"-> Checksums gravados em: {sha_file}")

    print("\n=== Empacotamento concluído com sucesso! ===")
    print(f"Diretório de distribuição: {dist_dir}")

if __name__ == "__main__":
    main()
