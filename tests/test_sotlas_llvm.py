"""Testes para o gerador de LLVM IR a partir do SIR."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.sir.instructions import (
    SIRModule, SIRFunction, SIRValue, AllocStackInst, StoreInst,
    LoadInst, CallInst, ReturnInst
)
from sotlas.codegen_llvm import CodegenLLVM, to_llvm_type


class TestCodegenLLVM(unittest.TestCase):
    def test_llvm_type_mapping(self):
        self.assertEqual(to_llvm_type("UInt32"), "i32")
        self.assertEqual(to_llvm_type("Int64"), "i64")
        self.assertEqual(to_llvm_type("Bool"), "i1")
        self.assertEqual(to_llvm_type("Void"), "void")
        self.assertEqual(to_llvm_type("*rawphys UInt8"), "ptr")

    def test_emit_simple_function(self):
        mod = SIRModule(name="test_mod")
        fn = SIRFunction(name="add_one", parameters=[SIRValue("x", "UInt32")], return_type="UInt32")
        bb0 = fn.add_block("0")
        
        alloc = AllocStackInst(var_name="res", type_name="UInt32", result=SIRValue("res_ptr", "*UInt32"))
        bb0.add(alloc)
        
        store = StoreInst(destination=SIRValue("res_ptr", "*UInt32"), source=SIRValue("x", "UInt32"))
        bb0.add(store)
        
        load = LoadInst(source=SIRValue("res_ptr", "*UInt32"), result=SIRValue("loaded", "UInt32"))
        bb0.add(load)
        
        ret = ReturnInst(value=SIRValue("loaded", "UInt32"))
        bb0.add(ret)
        
        mod.add_function(fn)
        
        codegen = CodegenLLVM(mod)
        llvm_ir = codegen.emit()
        
        self.assertIn("define i32 @add_one(i32 %x)", llvm_ir)
        self.assertIn("%res_ptr = alloca i32", llvm_ir)
        self.assertIn("store i32 %x, ptr %res_ptr", llvm_ir)
        self.assertIn("%loaded = load i32, ptr %res_ptr", llvm_ir)
        self.assertIn("ret i32 %loaded", llvm_ir)


if __name__ == "__main__":
    unittest.main()
