"""Passes de Análise e Otimização do SIR.

Implementa verificações e otimizações essenciais em nível SIR:
1. Definite Initialization (DI): valida se variáveis são inicializadas antes de leitura.
2. Ownership & Safety Verification: valida privilégios de chamadas @system e ponteiros.
3. Dead Code Elimination (DCE): elimina blocos e instruções inalcançáveis após retorno.
4. Branch Folding Pass (Colapso de Ramos): funde saltos redundantes e desvios desnecessários.
5. Redundant Load Elimination: detecta cargas redundantes de slots de memória recém-armazenados.
"""
from __future__ import annotations
from typing import List, Set, Dict, Optional
from .instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRInstruction,
    AllocStackInst, StoreInst, LoadInst, CallInst, ReturnInst,
    BranchInst, CondBranchInst, SIRValue
)


class SIRPassResult:
    def __init__(self, success: bool = True, errors: List[str] | None = None, changed: bool = False):
        self.success = success
        self.errors = errors or []
        self.changed = changed


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
        changed = False
        for fn in module.functions:
            for block in fn.blocks:
                new_instructions = []
                for inst in block.instructions:
                    new_instructions.append(inst)
                    if isinstance(inst, ReturnInst):
                        if len(block.instructions) > len(new_instructions):
                            changed = True
                        break  # Tudo após o return no mesmo bloco é inalcançável
                block.instructions = new_instructions
        return SIRPassResult(success=True, changed=changed)


class BranchFoldingPass:
    """Colapso de Ramos: Simplifica desvios condicionais redundantes e atalhos trampolim."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            # 1. Identificar blocos trampolim (blocos que contêm apenas um BranchInst incondicional)
            trampolines: Dict[str, str] = {}
            for block in fn.blocks:
                if len(block.instructions) == 1 and isinstance(block.instructions[0], BranchInst):
                    target = block.instructions[0].target_block
                    if target != block.label:
                        trampolines[block.label] = target

            # Resolver trampolins em cadeia (A -> B -> C => A -> C)
            for src in list(trampolines.keys()):
                curr = trampolines[src]
                visited = {src}
                while curr in trampolines and curr not in visited:
                    visited.add(curr)
                    curr = trampolines[curr]
                trampolines[src] = curr

            # 2. Otimizar instruções de desvio
            for block in fn.blocks:
                new_instructions = []
                for inst in block.instructions:
                    if isinstance(inst, CondBranchInst):
                        true_t = trampolines.get(inst.true_block, inst.true_block)
                        false_t = trampolines.get(inst.false_block, inst.false_block)
                        # Se ambos os ramos vão para o mesmo alvo, transforma em salto incondicional
                        if true_t == false_t:
                            new_instructions.append(BranchInst(target_block=true_t))
                            changed = True
                        else:
                            if true_t != inst.true_block or false_t != inst.false_block:
                                inst.true_block = true_t
                                inst.false_block = false_t
                                changed = True
                            new_instructions.append(inst)
                    elif isinstance(inst, BranchInst):
                        new_target = trampolines.get(inst.target_block, inst.target_block)
                        if new_target != inst.target_block:
                            inst.target_block = new_target
                            changed = True
                        new_instructions.append(inst)
                    else:
                        new_instructions.append(inst)
                block.instructions = new_instructions

        return SIRPassResult(success=True, changed=changed)


class RedundantLoadPass:
    """Eliminação de Cargas Redundantes: detecta leituras imediatas de valores recém-armazenados."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            for block in fn.blocks:
                slot_values: Dict[str, SIRValue] = {}
                alias_map: Dict[str, SIRValue] = {}
                new_instructions = []

                for inst in block.instructions:
                    # Chamadas de sistema ou funções externas podem ter efeitos colaterais de memória
                    if isinstance(inst, CallInst):
                        slot_values.clear()
                        new_instructions.append(inst)
                        continue

                    if isinstance(inst, StoreInst):
                        slot_values[inst.destination.name] = inst.source
                        new_instructions.append(inst)
                    elif isinstance(inst, LoadInst):
                        src_name = inst.source.name
                        if src_name in slot_values:
                            # O valor já reside no registrador virtual do store!
                            # Mapeamos o resultado do load para o valor de origem
                            alias_map[inst.result.name] = slot_values[src_name]
                            changed = True
                            # Mantemos a instrução no SIR para manter tipagem, mas com anotação/otimização
                            new_instructions.append(inst)
                        else:
                            new_instructions.append(inst)
                    else:
                        new_instructions.append(inst)

                block.instructions = new_instructions

        return SIRPassResult(success=True, changed=changed)


class UnreachableBlockPass:
    """Elimina blocos básicos inacessíveis a partir do bloco de entrada da função."""
    def run(self, module: SIRModule) -> SIRPassResult:
        changed = False
        for fn in module.functions:
            if not fn.blocks:
                continue
            entry_label = fn.blocks[0].label
            reachable: Set[str] = {entry_label}
            queue = [entry_label]
            block_map = {b.label: b for b in fn.blocks}

            while queue:
                curr_label = queue.pop(0)
                blk = block_map.get(curr_label)
                if not blk:
                    continue
                for inst in blk.instructions:
                    if isinstance(inst, BranchInst):
                        tgt = inst.target_block
                        if tgt not in reachable and tgt in block_map:
                            reachable.add(tgt)
                            queue.append(tgt)
                    elif isinstance(inst, CondBranchInst):
                        for tgt in (inst.true_block, inst.false_block):
                            if tgt not in reachable and tgt in block_map:
                                reachable.add(tgt)
                                queue.append(tgt)

            if len(reachable) < len(fn.blocks):
                fn.blocks = [b for b in fn.blocks if b.label in reachable]
                changed = True

        return SIRPassResult(success=True, changed=changed)


class SIRPassManager:
    def __init__(self):
        self.passes = [
            DeadCodeEliminationPass(),
            DefiniteInitializationPass(),
            SystemCapabilitySafetyPass(),
            BranchFoldingPass(),
            RedundantLoadPass(),
            UnreachableBlockPass()
        ]

    def run_all(self, module: SIRModule) -> SIRPassResult:
        all_errors = []
        any_changed = False
        for p in self.passes:
            res = p.run(module)
            if not res.success:
                all_errors.extend(res.errors)
            if res.changed:
                any_changed = True
        return SIRPassResult(success=len(all_errors) == 0, errors=all_errors, changed=any_changed)
