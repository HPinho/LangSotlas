"""Gerador de SIR a partir da AST do compilador Sotlas.

Mapeia declarações e corpos de função para blocos básicos SSA do SIR.
"""
from __future__ import annotations
from typing import Any, Optional
from .instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRValue,
    AllocStackInst, StoreInst, LoadInst, CallInst,
    ReturnInst, BranchInst, CondBranchInst, SystemOpInst
)


class SIRGenerator:
    def __init__(self, module_name: str = "main"):
        self.module_name = module_name
        self.sir_mod = SIRModule(name=module_name)
        self._val_counter = 0

    def _next_val(self, prefix: str = "v", type_name: str = "i32") -> SIRValue:
        v = SIRValue(name=f"{prefix}{self._val_counter}", type_name=type_name)
        self._val_counter += 1
        return v

    def generate_from_ast(self, ast: Any) -> SIRModule:
        """Gera o SIR a partir de um módulo AST parsed pelo frontend."""
        module_name = getattr(ast, "name", self.module_name)
        self.sir_mod = SIRModule(name=module_name)

        # Suporta nós de função tanto do frontend rico quanto do bootstrap
        functions = getattr(ast, "functions", None)
        if functions is None and hasattr(ast, "decls"):
            functions = [d for d in ast.decls if getattr(d, "__class__", None).__name__ == "FnDeclNode"]

        if functions:
            for fn in functions:
                self._lower_function(fn)

        return self.sir_mod

    def _lower_function(self, fn: Any) -> SIRFunction:
        fn_name = getattr(fn, "name", "anonymous")
        params = getattr(fn, "params", [])
        ret_type = getattr(fn, "ret", None) or getattr(fn, "result", None) or getattr(fn, "return_type", None)
        if isinstance(ret_type, str):
            ret_str = ret_type
        elif hasattr(ret_type, "name"):
            ret_str = ret_type.name
        else:
            ret_str = "void"
        directives = getattr(fn, "directives", []) or []
        dir_names = [getattr(d, "name", "") for d in directives]
        attrs = getattr(fn, "attributes", []) or []
        is_system = "@system" in attrs or "system" in dir_names or getattr(fn, "is_system", False)

        sir_params = []
        for p in params:
            p_name = getattr(p, "name", "arg")
            p_type = getattr(p, "type_ann", None) or getattr(p, "type", None)
            p_type_str = getattr(p_type, "name", "any") if p_type else "any"
            sir_params.append(SIRValue(name=p_name, type_name=p_type_str))

        sir_fn = SIRFunction(
            name=fn_name,
            parameters=sir_params,
            return_type=ret_str,
            is_system=is_system
        )
        self.sir_mod.add_function(sir_fn)

        entry_block = sir_fn.add_block("0")

        # Emite alocações para parâmetros locais
        for p in sir_params:
            stack_slot = self._next_val(f"slot_{p.name}", p.type_name)
            entry_block.add(AllocStackInst(var_name=p.name, type_name=p.type_name, result=stack_slot))
            entry_block.add(StoreInst(destination=stack_slot, source=p))

        # Emite retorno padrão caso o bloco não tenha finalizado
        entry_block.add(ReturnInst(value=None if ret_str == "void" else self._next_val("ret_val", ret_str)))
        return sir_fn
