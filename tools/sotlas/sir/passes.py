"""Passes de Análise e Otimização do SIR.

Implementa verificações essenciais em nível SIR:
1. Definite Initialization (DI): valida se variáveis são inicializadas antes de leitura.
2. Ownership & Safety Verification: valida privilégios de chamadas @system e ponteiros.
3. Dead Code Elimination (DCE): elimina blocos inalcançáveis.
"""
from __future__ import annotations
from typing import List, Set
from .instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRInstruction,
    AllocStackInst, StoreInst, LoadInst, CallInst, ReturnInst
)


class SIRPassResult:
    def __init__(self, success: bool = True, errors: List[str] | None = None):
        self.success = success
        self.errors = errors or []


class DefiniteInitializationPass:
    """Verifica se variáveis alocadas no stack recebem um store antes de qualquer load."""
    def run(self, module: SIRModule) -> SIRPassResult:
        errors = []
        for fn in module.functions:
            initialized_slots: Set[str] = set()
            for block in fn.blocks:
                for inst in block.instructions:
                    if isinstance(inst, StoreInst):
                        initialized_slots.add(inst.destination.name)
                    elif isinstance(inst, LoadInst):
                        if inst.source.name.startswith("slot_") and inst.source.name not in initialized_slots:
                            errors.append(
                                f"sir error: variável '{inst.source.name}' lida antes de ser inicializada na função '{fn.name}'"
                            )
        return SIRPassResult(success=len(errors) == 0, errors=errors)


class SystemCapabilitySafetyPass:
    """Verifica se operações marcadas com @system só são chamadas em contextos autorizados."""
    def run(self, module: SIRModule) -> SIRPassResult:
        errors = []
        for fn in module.functions:
            for block in fn.blocks:
                for inst in block.instructions:
                    if isinstance(inst, CallInst) and inst.is_system:
                        if not fn.is_system:
                            errors.append(
                                f"sir safety error: chamada para função @system '{inst.callee}' "
                                f"em função não-privilegiada '{fn.name}'"
                            )
        return SIRPassResult(success=len(errors) == 0, errors=errors)


class DeadCodeEliminationPass:
    """Identifica e remove instruções após return dentro do mesmo bloco básico."""
    def run(self, module: SIRModule) -> SIRPassResult:
        for fn in module.functions:
            for block in fn.blocks:
                new_instructions = []
                for inst in block.instructions:
                    new_instructions.append(inst)
                    if isinstance(inst, ReturnInst):
                        break  # Tudo após o return no mesmo bloco é inalcançável
                block.instructions = new_instructions
        return SIRPassResult(success=True)


class SIRPassManager:
    def __init__(self):
        self.passes = [
            DeadCodeEliminationPass(),
            DefiniteInitializationPass(),
            SystemCapabilitySafetyPass()
        ]

    def run_all(self, module: SIRModule) -> SIRPassResult:
        all_errors = []
        for p in self.passes:
            res = p.run(module)
            if not res.success:
                all_errors.extend(res.errors)
        return SIRPassResult(success=len(all_errors) == 0, errors=all_errors)
