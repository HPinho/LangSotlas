"""Sotlas Intermediate Representation (SIR) — Instruções SSA.

O SIR é uma representação estatisticamente tipada em formato SSA voltada para
análises de segurança de baixo nível, definite initialization e otimizações de ARC.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class SIRValue:
    name: str
    type_name: str

    def __repr__(self) -> str:
        return f"%{self.name}: {self.type_name}"


@dataclass
class SIRInstruction:
    """Instrução base do SIR."""
    pass


@dataclass
class AllocStackInst(SIRInstruction):
    var_name: str
    type_name: str
    result: SIRValue

    def __str__(self) -> str:
        return f"  {self.result} = alloc_stack {self.type_name} // {self.var_name}"


@dataclass
class StoreInst(SIRInstruction):
    destination: SIRValue
    source: SIRValue

    def __str__(self) -> str:
        return f"  store {self.source} to {self.destination}"


@dataclass
class LoadInst(SIRInstruction):
    source: SIRValue
    result: SIRValue

    def __str__(self) -> str:
        return f"  {self.result} = load {self.source}"


@dataclass
class CallInst(SIRInstruction):
    callee: str
    arguments: List[SIRValue]
    result: Optional[SIRValue] = None
    is_system: bool = False

    def __str__(self) -> str:
        prefix = f"{self.result} = " if self.result else ""
        sys_mark = "@system " if self.is_system else ""
        args_str = ", ".join(str(a) for a in self.arguments)
        return f"  {prefix}{sys_mark}call @{self.callee}({args_str})"


@dataclass
class RetainInst(SIRInstruction):
    value: SIRValue

    def __str__(self) -> str:
        return f"  retain_value {self.value}"


@dataclass
class ReleaseInst(SIRInstruction):
    value: SIRValue

    def __str__(self) -> str:
        return f"  release_value {self.value}"


@dataclass
class BranchInst(SIRInstruction):
    target_block: str

    def __str__(self) -> str:
        return f"  br bb{self.target_block}"


@dataclass
class CondBranchInst(SIRInstruction):
    condition: SIRValue
    true_block: str
    false_block: str

    def __str__(self) -> str:
        return f"  cond_br {self.condition}, bb{self.true_block}, bb{self.false_block}"


@dataclass
class ReturnInst(SIRInstruction):
    value: Optional[SIRValue] = None

    def __str__(self) -> str:
        if self.value:
            return f"  return {self.value}"
        return "  return void"


@dataclass
class SystemOpInst(SIRInstruction):
    operation: str
    operands: List[SIRValue]
    result: Optional[SIRValue] = None

    def __str__(self) -> str:
        prefix = f"{self.result} = " if self.result else ""
        ops_str = ", ".join(str(o) for o in self.operands)
        return f"  {prefix}system_op #{self.operation}({ops_str})"


@dataclass
class SIRBasicBlock:
    label: str
    instructions: List[SIRInstruction] = field(default_factory=list)

    def add(self, inst: SIRInstruction) -> None:
        self.instructions.append(inst)

    def __str__(self) -> str:
        lines = [f"bb{self.label}:"]
        for inst in self.instructions:
            lines.append(str(inst))
        return "\n".join(lines)


@dataclass
class SIRFunction:
    name: str
    parameters: List[SIRValue]
    return_type: str
    is_system: bool = False
    blocks: List[SIRBasicBlock] = field(default_factory=list)

    def add_block(self, label: str) -> SIRBasicBlock:
        b = SIRBasicBlock(label=label)
        self.blocks.append(b)
        return b

    def __str__(self) -> str:
        sys_tag = "@system " if self.is_system else ""
        params_str = ", ".join(str(p) for p in self.parameters)
        header = f"sir_fn {sys_tag}@{self.name}({params_str}) -> {self.return_type} {{"
        body = "\n".join(str(b) for b in self.blocks)
        return f"{header}\n{body}\n}}"


@dataclass
class SIRModule:
    name: str
    functions: List[SIRFunction] = field(default_factory=list)

    def add_function(self, fn: SIRFunction) -> None:
        self.functions.append(fn)

    def dump(self) -> str:
        lines = [f"// Sotlas Intermediate Representation (SIR) — Módulo {self.name}"]
        for fn in self.functions:
            lines.append(str(fn))
        return "\n\n".join(lines)
