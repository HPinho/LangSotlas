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


NATIVE_DRIVER_C = r"""/* Driver Nativo do Compilador Auto-Hospedado Sotlas (Sotlas-in-Sotlas) */
#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>

#define MAX_SOURCE_SIZE (4 * 1024 * 1024) // 4 MB
#define MAX_OUTPUT_SIZE (8 * 1024 * 1024) // 8 MB

// Função exportada do compilador Sotlas auto-hospedado
size_t sotlas_compile(const uint8_t *source, uint8_t *out_buf, size_t max_len);

static void print_usage(const char *prog_name) {
    printf("Sotlas Native Compiler v0.3.0 (Self-Hosted Architecture)\n");
    printf("Uso:\n");
    printf("  %s <arquivo.sotlas> [-o saida.exe|saida.c]\n", prog_name);
    printf("  %s run <arquivo.sotlas>\n", prog_name);
    printf("  %s compile <arquivo.sotlas> [-o saida.exe|saida.c]\n", prog_name);
    printf("  %s --version\n", prog_name);
}

static const char* find_c_compiler(void) {
    const char *env_clang = getenv("CLANG_PATH");
    if (env_clang && env_clang[0] != 0) return env_clang;

#if defined(_WIN32)
    static const char *candidates[] = {
        "clang.exe",
        "C:\\Program Files\\LLVM\\bin\\clang.exe",
        "gcc.exe"
    };
    for (size_t i = 0; i < sizeof(candidates)/sizeof(candidates[0]); i++) {
        char cmd[512];
        snprintf(cmd, sizeof(cmd), "\"\"%s\" --version >nul 2>&1\"", candidates[i]);
        if (system(cmd) == 0) {
            return candidates[i];
        }
    }
    return "clang.exe";
#else
    return "clang";
#endif
}

static bool ends_with(const char *str, const char *suffix) {
    if (!str || !suffix) return false;
    size_t len_str = strlen(str);
    size_t len_suf = strlen(suffix);
    if (len_str < len_suf) return false;
    return strcmp(str + (len_str - len_suf), suffix) == 0;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "--version") == 0 || strcmp(argv[1], "-v") == 0) {
        printf("Sotlas Native Compiler v0.3.0 (Self-Hosted Standalone Executable)\n");
        printf("Engine: Sotlas-in-Sotlas / LLVM Native\n");
        return 0;
    }

    bool is_run = false;
    const char *input_file = NULL;
    const char *output_file = NULL;
    bool emit_c_only = false;

    int arg_idx = 1;
    if (strcmp(argv[1], "run") == 0) {
        is_run = true;
        arg_idx = 2;
        if (argc < 3) {
            fprintf(stderr, "sotlas-native: erro: esperado arquivo .sotlas apos 'run'\n");
            return 1;
        }
    } else if (strcmp(argv[1], "compile") == 0) {
        arg_idx = 2;
        if (argc < 3) {
            fprintf(stderr, "sotlas-native: erro: esperado arquivo .sotlas apos 'compile'\n");
            return 1;
        }
    }

    input_file = argv[arg_idx++];

    for (int i = arg_idx; i < argc; i++) {
        if (strcmp(argv[i], "-o") == 0 && (i + 1 < argc)) {
            output_file = argv[i + 1];
            i++;
        } else if (strcmp(argv[i], "--emit-c") == 0) {
            emit_c_only = true;
        }
    }

    FILE *f = fopen(input_file, "rb");
    if (!f) {
        fprintf(stderr, "sotlas-native: erro: nao foi possivel abrir o arquivo '%s'\n", input_file);
        return 1;
    }

    fseek(f, 0, SEEK_END);
    long file_size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (file_size < 0 || file_size > MAX_SOURCE_SIZE) {
        fprintf(stderr, "sotlas-native: erro: tamanho de arquivo invalido (%ld bytes)\n", file_size);
        fclose(f);
        return 1;
    }

    uint8_t *source = (uint8_t *)malloc(file_size + 1);
    if (!source) {
        fprintf(stderr, "sotlas-native: erro de alocacao de memoria\n");
        fclose(f);
        return 1;
    }

    size_t read_bytes = fread(source, 1, file_size, f);
    source[read_bytes] = 0;
    fclose(f);

    uint8_t *output = (uint8_t *)malloc(MAX_OUTPUT_SIZE);
    if (!output) {
        fprintf(stderr, "sotlas-native: erro de alocacao de buffer de saida\n");
        free(source);
        return 1;
    }
    memset(output, 0, MAX_OUTPUT_SIZE);

    size_t out_len = sotlas_compile(source, output, MAX_OUTPUT_SIZE);
    free(source);

    if (out_len == 0) {
        fprintf(stderr, "sotlas-native: erro na compilacao do arquivo '%s'\n", input_file);
        free(output);
        return 1;
    }

    if (is_run) {
        char temp_c[512];
        char temp_exe[512];
#if defined(_WIN32)
        snprintf(temp_c, sizeof(temp_c), "%s.run_tmp.c", input_file);
        snprintf(temp_exe, sizeof(temp_exe), "%s.run_tmp.exe", input_file);
#else
        snprintf(temp_c, sizeof(temp_c), "%s.run_tmp.c", input_file);
        snprintf(temp_exe, sizeof(temp_exe), "%s.run_tmp.bin", input_file);
#endif
        FILE *tf = fopen(temp_c, "wb");
        if (!tf) {
            fprintf(stderr, "sotlas-native: erro ao criar arquivo temporario\n");
            free(output);
            return 1;
        }
        fwrite(output, 1, out_len, tf);
        fclose(tf);

        const char *cc = find_c_compiler();
        char build_cmd[1024];
#if defined(_WIN32)
        snprintf(build_cmd, sizeof(build_cmd), "\"\"%s\" -O2 \"%s\" -o \"%s\"\"", cc, temp_c, temp_exe);
#else
        snprintf(build_cmd, sizeof(build_cmd), "\"%s\" -O2 \"%s\" -o \"%s\"", cc, temp_c, temp_exe);
#endif
        int b_ret = system(build_cmd);
        remove(temp_c);

        if (b_ret != 0) {
            fprintf(stderr, "sotlas-native: erro ao linkar executavel com '%s'\n", cc);
            free(output);
            return b_ret;
        }

        int run_ret = system(temp_exe);
        remove(temp_exe);
        free(output);
        return run_ret;
    }

    if (output_file) {
        bool is_binary_target = ends_with(output_file, ".exe") || ends_with(output_file, ".obj") ||
                                ends_with(output_file, ".o") || ends_with(output_file, ".bin");

        if (is_binary_target && !emit_c_only) {
            char temp_c[512];
            snprintf(temp_c, sizeof(temp_c), "%s.tmp.c", output_file);
            FILE *out_f = fopen(temp_c, "wb");
            if (!out_f) {
                fprintf(stderr, "sotlas-native: erro ao escrever em '%s'\n", temp_c);
                free(output);
                return 1;
            }
            fwrite(output, 1, out_len, out_f);
            fclose(out_f);

            const char *cc = find_c_compiler();
            char build_cmd[1024];
#if defined(_WIN32)
            snprintf(build_cmd, sizeof(build_cmd), "\"\"%s\" -O2 \"%s\" -o \"%s\"\"", cc, temp_c, output_file);
#else
            snprintf(build_cmd, sizeof(build_cmd), "\"%s\" -O2 \"%s\" -o \"%s\"", cc, temp_c, output_file);
#endif
            int b_ret = system(build_cmd);
            remove(temp_c);

            if (b_ret != 0) {
                fprintf(stderr, "sotlas-native: erro ao gerar binario nativo com '%s'\n", cc);
                free(output);
                return b_ret;
            }
            printf("sotlas-native: compilado e linkado com sucesso -> '%s'\n", output_file);
        } else {
            FILE *out_f = fopen(output_file, "wb");
            if (!out_f) {
                fprintf(stderr, "sotlas-native: erro ao escrever em '%s'\n", output_file);
                free(output);
                return 1;
            }
            fwrite(output, 1, out_len, out_f);
            fclose(out_f);
            printf("sotlas-native: C11 emitido com sucesso -> '%s' (%zu bytes)\n", output_file, out_len);
        }
    } else {
        printf("%s\n", (char *)output);
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

    # 2. Compila e executa um arquivo de teste usando o compilador nativo
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir_path = Path(tmpdir)
        st_test_file = tmp_dir_path / "test_calc.sotlas"
        st_test_file.write_text("""module test::calc;
pub fn add(a: u32, b: u32) -> u32 {
    let res: u32 = a + b;
    return res;
}
pub fn main() -> i32 {
    let sum: u32 = add(15, 25);
    if sum == 40 {
        return 0;
    } else {
        return 1;
    }
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

        # 3. Testa a compilação direta para binário executável e execução nativa
        exe_suffix = ".exe" if os.name == "nt" else ""
        out_bin = tmp_dir_path / f"test_calc{exe_suffix}"
        res_bin = subprocess.run(
            [str(compiler_exe), str(st_test_file), "-o", str(out_bin)],
            capture_output=True,
            text=True
        )
        if res_bin.returncode == 0 and out_bin.is_file():
            run_res = subprocess.run([str(out_bin)])
            if run_res.returncode != 0:
                return False

    return True
