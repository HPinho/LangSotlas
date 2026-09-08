"""Sotlas Bootstrap Pipeline — Compilação e Verificação do Compilador Auto-Hospedado (Self-Hosting).

Este módulo orquestra a geração do compilador nativo Sotlas escrito na própria linguagem
Sotlas (bootstrap/sotlas/sotlas_lite/), produzindo o executável binário standalone `sotlas_native.exe`
sem qualquer dependência de runtime do Python.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from sotlas.llvm_toolchain import default_toolchain, LLVMToolchainError


_ROOT = Path(__file__).resolve().parent.parent.parent
BOOTSTRAP_SOURCE_DIR = _ROOT / "bootstrap" / "sotlas" / "sotlas_lite"
BOOTSTRAP_ENTRY = BOOTSTRAP_SOURCE_DIR / "main.sotlas"


NATIVE_DRIVER_C = """/* Driver Nativo do Compilador Auto-Hospedado Sotlas (Sotlas-in-Sotlas) */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>

#define MAX_SOURCE_SIZE (2 * 1024 * 1024) // 2 MB
#define MAX_OUTPUT_SIZE (4 * 1024 * 1024) // 4 MB

// Função exportada do compilador Sotlas auto-hospedado
size_t sotlas_compile(const uint8_t *source, uint8_t *out_buf, size_t max_len);

static void print_usage(const char *prog_name) {
    printf("Sotlas Native Compiler v0.3.0 (Self-Hosted Architecture)\\n");
    printf("Uso:\\n");
    printf("  %s <arquivo.sotlas> [-o saida.c]\\n", prog_name);
    printf("  %s --version\\n", prog_name);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "--version") == 0 || strcmp(argv[1], "-v") == 0) {
        printf("Sotlas Native Compiler v0.3.0 (Self-Hosted Standalone Executable)\\n");
        printf("Engine: Sotlas-in-Sotlas / LLVM Native\\n");
        return 0;
    }

    const char *input_file = argv[1];
    const char *output_file = NULL;

    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "-o") == 0 && (i + 1 < argc)) {
            output_file = argv[i + 1];
            i++;
        }
    }

    FILE *f = fopen(input_file, "rb");
    if (!f) {
        fprintf(stderr, "sotlas-native: erro: nao foi possivel abrir o arquivo '%s'\\n", input_file);
        return 1;
    }

    fseek(f, 0, SEEK_END);
    long file_size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (file_size < 0 || file_size > MAX_SOURCE_SIZE) {
        fprintf(stderr, "sotlas-native: erro: tamanho de arquivo invalido (%ld bytes)\\n", file_size);
        fclose(f);
        return 1;
    }

    uint8_t *source = (uint8_t *)malloc(file_size + 1);
    if (!source) {
        fprintf(stderr, "sotlas-native: erro de alocacao de memoria\\n");
        fclose(f);
        return 1;
    }

    size_t read_bytes = fread(source, 1, file_size, f);
    source[read_bytes] = 0;
    fclose(f);

    uint8_t *output = (uint8_t *)malloc(MAX_OUTPUT_SIZE);
    if (!output) {
        fprintf(stderr, "sotlas-native: erro de alocacao de buffer de saida\\n");
        free(source);
        return 1;
    }
    memset(output, 0, MAX_OUTPUT_SIZE);

    size_t out_len = sotlas_compile(source, output, MAX_OUTPUT_SIZE);
    free(source);

    if (out_len == 0) {
        fprintf(stderr, "sotlas-native: erro na compilacao do arquivo '%s'\\n", input_file);
        free(output);
        return 1;
    }

    if (output_file) {
        FILE *out_f = fopen(output_file, "wb");
        if (!out_f) {
            fprintf(stderr, "sotlas-native: erro ao escrever em '%s'\\n", output_file);
            free(output);
            return 1;
        }
        fwrite(output, 1, out_len, out_f);
        fclose(out_f);
        printf("sotlas-native: compilado com sucesso -> '%s' (%zu bytes)\\n", output_file, out_len);
    } else {
        printf("%s\\n", (char *)output);
    }

    free(output);
    return 0;
}
"""


def build_self_hosted_compiler(
    output_exe: Optional[Path] = None,
    verbose: bool = True
) -> Path:
    """Compila o compilador Sotlas em Sotlas e produz o binário nativo `sotlas_native.exe`."""
    if not default_toolchain.is_available():
        raise LLVMToolchainError("Toolchain LLVM / Clang necessária para o bootstrap não foi encontrada.")

    if output_exe is None:
        build_dir = _ROOT / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        exe_suffix = ".exe" if os.name == "nt" else ""
        output_exe = build_dir / f"sotlas_native{exe_suffix}"

    output_exe = output_exe.resolve()
    output_exe.parent.mkdir(parents=True, exist_ok=True)

    # 1. Transpila o projeto Sotlas-lite para C11 usando o bootstrap Stage 0
    from sotlas_compile import bootstrap as stage0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir_path = Path(tmpdir)
        compiler_c = tmp_dir_path / "sotlas_compiler_lite.c"
        driver_c = tmp_dir_path / "sotlas_native_driver.c"

        if verbose:
            print(f"sotlas bootstrap: compilando {BOOTSTRAP_ENTRY}...")

        stage0.emit_c_project(BOOTSTRAP_ENTRY, compiler_c)
        driver_c.write_text(NATIVE_DRIVER_C, encoding="utf-8")

        # 2. Compila ambos os arquivos com Clang nativo para arquivos objeto .obj
        compiler_obj = tmp_dir_path / "compiler.obj"
        driver_obj = tmp_dir_path / "driver.obj"

        if verbose:
            print("sotlas bootstrap: compilando objetos nativos via Clang...")

        default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=2)
        default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=2)

        # 3. Linkedita o binário nativo com LLD / Clang
        if verbose:
            print(f"sotlas bootstrap: linkedição final -> {output_exe}...")

        default_toolchain.link_native_binary([compiler_obj, driver_obj], output_exe)

    if verbose:
        print(f"sotlas bootstrap: compilador auto-hospedado gerado com sucesso em {output_exe}")

    return output_exe


def verify_self_hosted_compiler(compiler_exe: Path) -> bool:
    """Verifica a funcionalidade do compilador auto-hospedado executando um teste de compilação."""
    if not compiler_exe.is_file():
        return False

    # 1. Verifica --version
    res_ver = subprocess.run([str(compiler_exe), "--version"], capture_output=True, text=True)
    if res_ver.returncode != 0 or "Sotlas Native Compiler" not in res_ver.stdout:
        return False

    # 2. Compila um arquivo de teste usando o compilador nativo
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir_path = Path(tmpdir)
        st_test_file = tmp_dir_path / "test_calc.sotlas"
        st_test_file.write_text("""module test::calc;
pub fn add(a: u32, b: u32) -> u32 {
    let res: u32 = a + b;
    return res;
}
""", encoding="utf-8")

        out_c_file = tmp_dir_path / "test_calc.c"
        res_comp = subprocess.run(
            [str(compiler_exe), str(st_test_file), "-o", str(out_c_file)],
            capture_output=True,
            text=True
        )

        if res_comp.returncode != 0 or not out_c_file.is_file():
            return False

        c_content = out_c_file.read_text(encoding="utf-8")
        if "uint32_t" not in c_content or "add" not in c_content:
            return False

    return True
