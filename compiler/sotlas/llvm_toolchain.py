"""Sotlas LLVM Toolchain — Orquestrador de Emissão Direta de Código Objeto e Binários Nativos via LLVM / LLD.

Este módulo localiza a instalação do LLVM (Clang, LLD, LLC, LLDB),
executa a compilação direta de LLVM IR textual (.ll) ou código C11 gerado
para código objeto nativo (.o / .obj) e linkedita executáveis nativos standalone (.exe / ELF),
eliminando a necessidade de qualquer compilador C externo clássico (GCC).
"""
from __future__ import annotations
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Union


# Locais canônicos de busca de ferramentas LLVM
DEFAULT_LLVM_PATHS = [
    Path(r"C:\Program Files\LLVM\bin"),
    Path(r"C:\Program Files (x86)\LLVM\bin"),
    Path(r"C:\LLVM\bin"),
    Path("/usr/local/opt/llvm/bin"),
    Path("/usr/lib/llvm/bin"),
    Path("/usr/bin"),
]


class LLVMToolchainError(Exception):
    """Erro emitido durante a execução de ferramentas da toolchain LLVM."""
    pass


class LLVMToolchain:
    """Gerenciador e orquestrador de compilação nativa via LLVM / LLD."""

    def __init__(self, custom_llvm_dir: Optional[Union[str, Path]] = None) -> None:
        self.llvm_dir: Optional[Path] = None
        if custom_llvm_dir:
            p = Path(custom_llvm_dir)
            if p.is_dir():
                self.llvm_dir = p

        if not self.llvm_dir:
            env_dir = os.environ.get("SOTLAS_LLVM_DIR")
            if env_dir and Path(env_dir).is_dir():
                self.llvm_dir = Path(env_dir)

        if not self.llvm_dir:
            for candidate in DEFAULT_LLVM_PATHS:
                if candidate.is_dir() and (candidate / ("clang.exe" if os.name == "nt" else "clang")).exists():
                    self.llvm_dir = candidate
                    break

    def find_tool(self, tool_name: str) -> Optional[Path]:
        """Localiza uma ferramenta LLVM específica (ex: 'clang', 'lld-link', 'llc', 'lldb')."""
        exe_suffix = ".exe" if os.name == "nt" else ""
        canonical_name = f"{tool_name}{exe_suffix}"

        if self.llvm_dir:
            candidate = self.llvm_dir / canonical_name
            if candidate.is_file():
                return candidate

        # Tenta no PATH do sistema
        which_path = shutil.which(tool_name)
        if which_path:
            return Path(which_path)

        return None

    def is_available(self) -> bool:
        """Verifica se o compilador Clang / LLVM está acessível no ambiente."""
        return self.find_tool("clang") is not None

    def get_version(self) -> str:
        """Retorna a versão do Clang / LLVM instalado."""
        clang = self.find_tool("clang")
        if not clang:
            return "Indisponível"
        try:
            res = subprocess.run([str(clang), "--version"], capture_output=True, text=True, check=True)
            first_line = res.stdout.splitlines()[0] if res.stdout else ""
            return first_line.strip()
        except Exception as e:
            return f"Erro ao detectar versão: {e}"

    def compile_llvm_ir_to_obj(
        self,
        ir_path_or_text: Union[str, Path],
        output_obj_path: Union[str, Path],
        opt_level: int = 2,
        target: Optional[str] = None
    ) -> Path:
        """Compila LLVM IR (.ll) diretamente para arquivo objeto (.obj / .o)."""
        clang = self.find_tool("clang")
        if not clang:
            raise LLVMToolchainError("Compilador Clang / LLVM não encontrado no sistema.")

        out_obj = Path(output_obj_path).resolve()
        out_obj.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(clang), "-c", f"-O{opt_level}"]
        if target:
            cmd += ["-target", target]

        temp_ir = None
        try:
            if isinstance(ir_path_or_text, Path) or (isinstance(ir_path_or_text, str) and os.path.exists(ir_path_or_text)):
                input_file = str(ir_path_or_text)
            else:
                # É código textual
                fd, temp_ir = tempfile.mkstemp(suffix=".ll", prefix="sotlas_ir_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(str(ir_path_or_text))
                input_file = temp_ir

            cmd += [input_file, "-o", str(out_obj)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise LLVMToolchainError(f"Falha na compilação LLVM IR -> OBJ:\n{res.stderr}")

            return out_obj
        finally:
            if temp_ir and os.path.exists(temp_ir):
                try:
                    os.remove(temp_ir)
                except OSError:
                    pass

    def compile_c_to_obj(
        self,
        c_path_or_text: Union[str, Path],
        output_obj_path: Union[str, Path],
        opt_level: int = 2,
        is_freestanding: bool = False,
        extra_flags: Optional[List[str]] = None
    ) -> Path:
        """Compila código C11 diretamente para arquivo objeto nativo (.obj / .o) via Clang."""
        clang = self.find_tool("clang")
        if not clang:
            raise LLVMToolchainError("Compilador Clang / LLVM não encontrado no sistema.")

        out_obj = Path(output_obj_path).resolve()
        out_obj.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(clang), "-std=c11", "-c", f"-O{opt_level}", "-Wall", "-Wextra"]
        if is_freestanding:
            cmd += [
                "-ffreestanding", "-nostdlib", "-nostdinc",
                "-mno-red-zone", "-mno-mmx", "-mno-sse", "-mno-sse2"
            ]
        if extra_flags:
            cmd += extra_flags

        temp_c = None
        try:
            if isinstance(c_path_or_text, Path) or (isinstance(c_path_or_text, str) and os.path.exists(c_path_or_text)):
                input_file = str(c_path_or_text)
            else:
                fd, temp_c = tempfile.mkstemp(suffix=".c", prefix="sotlas_c_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(str(c_path_or_text))
                input_file = temp_c

            cmd += [input_file, "-o", str(out_obj)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise LLVMToolchainError(f"Falha na compilação C11 -> OBJ com Clang:\n{res.stderr}")

            return out_obj
        finally:
            if temp_c and os.path.exists(temp_c):
                try:
                    os.remove(temp_c)
                except OSError:
                    pass

    def link_native_binary(
        self,
        obj_files: List[Union[str, Path]],
        output_exe_path: Union[str, Path],
        extra_flags: Optional[List[str]] = None
    ) -> Path:
        """Linkedita um ou mais arquivos objeto em um executável nativo standalone (.exe / binário)."""
        clang = self.find_tool("clang")
        if not clang:
            raise LLVMToolchainError("Linker Clang / LLVM não encontrado no sistema.")

        out_exe = Path(output_exe_path).resolve()
        out_exe.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(clang)] + [str(p) for p in obj_files] + ["-o", str(out_exe)]
        if extra_flags:
            cmd += extra_flags

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise LLVMToolchainError(f"Falha na linkedição nativa com Clang / LLD:\n{res.stderr}")

        return out_exe

    def compile_source_to_native(
        self,
        source_text: str,
        source_name: str,
        output_path: Union[str, Path],
        emit_type: str = "exe",  # "exe", "obj", "llvm"
        backend: str = "llvm",   # "llvm", "c11"
        is_freestanding: bool = False,
        emit_debug: bool = True
    ) -> Path:
        """Pipeline fim a fim: compila código-fonte Sotlas diretamente para .ll, .obj ou .exe."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        from sotlas.sir import SIRGenerator
        from sotlas.codegen_llvm import CodegenLLVM
        from sotlas_compile import bootstrap as production_frontend
        from sotlas import compile_source

        if emit_type == "llvm":
            ast = production_frontend.parse(source_text, filename=source_name)
            sir_gen = SIRGenerator(module_name=source_name)
            sir_mod = sir_gen.generate_from_ast(ast)
            llvm_gen = CodegenLLVM(sir_mod, is_baremetal=is_freestanding, emit_debug=emit_debug)
            ir_code = llvm_gen.emit()
            out.write_text(ir_code, encoding="utf-8")
            return out

        safe_stem = re.sub(r'[^a-zA-Z0-9_]', '_', Path(source_name).stem) or "sotlas_module"

        if backend == "llvm":
            ast = production_frontend.parse(source_text, filename=source_name)
            sir_gen = SIRGenerator(module_name=source_name)
            sir_mod = sir_gen.generate_from_ast(ast)
            llvm_gen = CodegenLLVM(sir_mod, is_baremetal=is_freestanding, emit_debug=emit_debug)
            ir_code = llvm_gen.emit()

            if emit_type == "obj":
                return self.compile_llvm_ir_to_obj(ir_code, out)
            else:
                # Compila para obj temporário e linka para exe
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_obj = Path(tmpdir) / f"{safe_stem}.obj"
                    self.compile_llvm_ir_to_obj(ir_code, tmp_obj)
                    return self.link_native_binary([tmp_obj], out)
        else:
            # Backend c11 com Clang nativo
            c_code = compile_source(source_text, source_name)
            if emit_type == "obj":
                return self.compile_c_to_obj(c_code, out, is_freestanding=is_freestanding)
            else:
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_obj = Path(tmpdir) / f"{safe_stem}.obj"
                    self.compile_c_to_obj(c_code, tmp_obj, is_freestanding=is_freestanding)
                    return self.link_native_binary([tmp_obj], out)


# Instância global padrão da toolchain
default_toolchain = LLVMToolchain()
