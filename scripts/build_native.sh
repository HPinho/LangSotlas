#!/usr/bin/env bash
set -e

echo "======================================================="
echo "  Sotlas Native Compiler Autonomous Build (Zero-Python)"
echo "======================================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p build bin

# 1. Locate C compiler
CC="${CC:-}"
if [ -z "$CC" ]; then
    if command -v clang >/dev/null 2>&1; then
        CC="clang"
    elif command -v gcc >/dev/null 2>&1; then
        CC="gcc"
    else
        echo "[ERROR] No C compiler found (clang or gcc on PATH)."
        exit 1
    fi
fi
echo "[OK] C compiler detected: $CC"

# 2. Check if native binary already exists for pure self-compile
if [ -x "bin/sotlas_native" ]; then
    echo "[INFO] Existing native binary detected at bin/sotlas_native."
    echo "[INFO] Performing pure self-compilation (Zero-Python)..."
    bin/sotlas_native "bootstrap/sotlas/sotlas_lite/main.sotlas" -o "build/sotlas_compiler_stage2.c"
    "$CC" -O2 "build/sotlas_compiler_stage2.c" "bootstrap/sotlas/sotlas_lite/sotlas_native_driver.c" -o "bin/sotlas_native"
    echo "[SUCCESS] Native compiler updated via pure self-compilation!"
    bin/sotlas_native --version
    exit 0
fi

echo "[INFO] Generating initial native compiler..."
python3 -c "import sys; from pathlib import Path; sys.path.insert(0, 'compiler'); from sotlas.bootstrap_pipeline import build_self_hosted_compiler; build_self_hosted_compiler(Path('bin/sotlas_native'))"

echo "[INFO] Validating Stage 2 self-compilation via sotlas_native..."
bin/sotlas_native "bootstrap/sotlas/sotlas_lite/main.sotlas" -o "build/sotlas_compiler_stage2.c"
echo "[SUCCESS] Sotlas native compiler ready: bin/sotlas_native"
bin/sotlas_native --version
exit 0
