"""Sotlas Intermediate Representation (SIR).

Módulo que implementa a representação intermediária em formato SSA
para análises estáticas de segurança e otimizações de baixo nível.
"""

from .instructions import (
    SIRValue,
    SIRInstruction,
    AllocStackInst,
    StoreInst,
    LoadInst,
    CallInst,
    RetainInst,
    ReleaseInst,
    BranchInst,
    CondBranchInst,
    ReturnInst,
    SystemOpInst,
    SIRBasicBlock,
    SIRFunction,
    SIRModule,
)
from .generator import SIRGenerator
from .passes import (
    SIRPassResult,
    SIRPassManager,
    DefiniteInitializationPass,
    SystemCapabilitySafetyPass,
    DeadCodeEliminationPass,
)

__all__ = [
    "SIRValue",
    "SIRInstruction",
    "AllocStackInst",
    "StoreInst",
    "LoadInst",
    "CallInst",
    "RetainInst",
    "ReleaseInst",
    "BranchInst",
    "CondBranchInst",
    "ReturnInst",
    "SystemOpInst",
    "SIRBasicBlock",
    "SIRFunction",
    "SIRModule",
    "SIRGenerator",
    "SIRPassResult",
    "SIRPassManager",
    "DefiniteInitializationPass",
    "SystemCapabilitySafetyPass",
    "DeadCodeEliminationPass",
]
