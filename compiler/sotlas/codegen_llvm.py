"""Sotlas CodegenLLVM — Gerador de LLVM IR a partir do SIR (Estágio 1).

Este módulo transcreve o SIR (SSA) de Sotlas para LLVM IR textual (.ll),
fornecendo a base para o backend nativo sem dependência de transcompilação C99.
"""
from __future__ import annotations
from io import StringIO
from typing import Dict, List, Optional
from .sir.instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRInstruction, SIRValue,
    AllocStackInst, StoreInst, LoadInst, CallInst, RetainInst, ReleaseInst,
    BranchInst, CondBranchInst, ReturnInst, SystemOpInst
)


LLVM_TYPE_MAP: Dict[str, str] = {
    "Void": "void",
    "void": "void",
    "Bool": "i1",
    "UInt8": "i8",
    "Int8": "i8",
    "u8": "i8",
    "i8": "i8",
    "UInt16": "i16",
    "Int16": "i16",
    "u16": "i16",
    "i16": "i16",
    "UInt32": "i32",
    "Int32": "i32",
    "u32": "i32",
    "i32": "i32",
    "UInt64": "i64",
    "Int64": "i64",
    "u64": "i64",
    "i64": "i64",
    "Int": "i64",
    "UInt": "i64",
    "Float32": "float",
    "f32": "float",
    "Float64": "double",
    "f64": "double",
}


def to_llvm_type(sotlas_type: Optional[str]) -> str:
    """Mapeia tipos primitivos e ponteiros de Sotlas para tipos do LLVM IR."""
    if not sotlas_type:
        return "void"
    s = str(sotlas_type)
    if s.startswith("*") or s.endswith("*") or "ptr" in s:
        return "ptr"
    return LLVM_TYPE_MAP.get(s, "i64")


class CodegenLLVM:
    """Emissor de LLVM IR textual para módulos SIR."""

    def __init__(self, sir_module: SIRModule, is_baremetal: bool = True) -> None:
        self._sir = sir_module
        self._is_baremetal = is_baremetal
        self._out = StringIO()

    def emit(self) -> str:
        self._emit_header()
        for fn in self._sir.functions:
            self._emit_function(fn)
        return self._out.getvalue()

    def _emit_header(self) -> None:
        self._out.write(f"; ModuleID = '{self._sir.name}'\n")
        self._out.write(f"source_filename = \"{self._sir.name}.sotlas\"\n")
        if self._is_baremetal:
            self._out.write("target datalayout = \"e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128\"\n")
            self._out.write("target triple = \"x86_64-unknown-none-elf\"\n\n")
        else:
            self._out.write("target triple = \"x86_64-pc-none\"\n\n")

    def _emit_function(self, fn: SIRFunction) -> None:
        ret_type = to_llvm_type(fn.return_type)
        params_str = ", ".join(f"{to_llvm_type(p.type_name)} %{p.name}" for p in fn.parameters)
        self._out.write(f"define {ret_type} @{fn.name}({params_str}) #0 {{\n")

        for block in fn.blocks:
            lbl_str = str(block.label)
            label = f"bb{lbl_str}" if not lbl_str.startswith("bb") else lbl_str
            self._out.write(f"{label}:\n")
            for inst in block.instructions:
                self._emit_instruction(inst)

        self._out.write("}\n\n")

    def _emit_instruction(self, inst: SIRInstruction) -> None:
        if isinstance(inst, AllocStackInst):
            llvm_type = to_llvm_type(inst.type_name)
            self._out.write(f"  %{inst.result.name} = alloca {llvm_type}, align 8\n")
        elif isinstance(inst, StoreInst):
            src_type = to_llvm_type(inst.source.type_name)
            self._out.write(f"  store {src_type} %{inst.source.name}, ptr %{inst.destination.name}, align 8\n")
        elif isinstance(inst, LoadInst):
            res_type = to_llvm_type(inst.result.type_name)
            self._out.write(f"  %{inst.result.name} = load {res_type}, ptr %{inst.source.name}, align 8\n")
        elif isinstance(inst, CallInst):
            res_type = to_llvm_type(inst.result.type_name) if inst.result else "void"
            args_str = ", ".join(f"{to_llvm_type(a.type_name)} %{a.name}" for a in inst.arguments)
            if inst.result:
                self._out.write(f"  %{inst.result.name} = call {res_type} @{inst.callee}({args_str})\n")
            else:
                self._out.write(f"  call {res_type} @{inst.callee}({args_str})\n")
        elif isinstance(inst, RetainInst):
            self._out.write(f"  ; arc retain %{inst.value.name}\n")
        elif isinstance(inst, ReleaseInst):
            self._out.write(f"  ; arc release %{inst.value.name}\n")
        elif isinstance(inst, BranchInst):
            t_str = str(inst.target_block)
            target = f"bb{t_str}" if not t_str.startswith("bb") else t_str
            self._out.write(f"  br label %{target}\n")
        elif isinstance(inst, CondBranchInst):
            tb = str(inst.true_block)
            fb = str(inst.false_block)
            true_b = f"bb{tb}" if not tb.startswith("bb") else tb
            false_b = f"bb{fb}" if not fb.startswith("bb") else fb
            self._out.write(f"  br i1 %{inst.condition.name}, label %{true_b}, label %{false_b}\n")
        elif isinstance(inst, ReturnInst):
            if inst.value:
                val_type = to_llvm_type(inst.value.type_name)
                self._out.write(f"  ret {val_type} %{inst.value.name}\n")
            else:
                self._out.write("  ret void\n")
        elif isinstance(inst, SystemOpInst):
            self._out.write(f"  ; system_op #{inst.operation}\n")
