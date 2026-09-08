"""Testes unitários para o Sotlas Intermediate Representation (SIR)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.sir import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRValue,
    AllocStackInst, StoreInst, LoadInst, CallInst, ReturnInst,
    SIRGenerator, SIRPassManager, DefiniteInitializationPass,
    SystemCapabilitySafetyPass, DeadCodeEliminationPass
)
from sotlas.lexer import Lexer
from sotlas.parser import Parser


class SotlasSIRTests(unittest.TestCase):
    def test_sir_instruction_string_representation(self):
        v0 = SIRValue("v0", "i32")
        v1 = SIRValue("v1", "i32")
        alloc = AllocStackInst("count", "i32", v0)
        store = StoreInst(v0, v1)
        load = LoadInst(v0, v1)
        call = CallInst("display_init", [v0], is_system=True)
        ret = ReturnInst(v1)

        self.assertIn("alloc_stack i32 // count", str(alloc))
        self.assertIn("store %v1: i32 to %v0: i32", str(store))
        self.assertIn("%v1: i32 = load %v0: i32", str(load))
        self.assertIn("@system call @display_init", str(call))
        self.assertIn("return %v1: i32", str(ret))

    def test_sir_generator_from_ast(self):
        source = """
        module test::sir_probe;

        @system
        pub fn compute_sum(a: i32, b: i32) -> i32 {
            return a + b;
        }
        """
        tokens = Lexer(source, "<sir-probe>").tokenize()
        ast = Parser(tokens, "<sir-probe>").parse()

        generator = SIRGenerator()
        sir_mod = generator.generate_from_ast(ast)

        self.assertEqual(len(sir_mod.functions), 1)
        fn = sir_mod.functions[0]
        self.assertEqual(fn.name, "compute_sum")
        self.assertTrue(fn.is_system)
        self.assertEqual(len(fn.parameters), 2)
        dump = sir_mod.dump()
        self.assertIn("sir_fn @system @compute_sum", dump)
        self.assertIn("alloc_stack", dump)

    def test_definite_initialization_pass_detects_uninitialized_read(self):
        fn = SIRFunction("bad_fn", [], "i32")
        b = fn.add_block("0")
        slot = SIRValue("slot_uninit", "i32")
        res = SIRValue("res", "i32")
        b.add(AllocStackInst("uninit", "i32", slot))
        b.add(LoadInst(slot, res))  # Leitura antes do store!
        b.add(ReturnInst(res))

        mod = SIRModule("test_di")
        mod.add_function(fn)

        di_pass = DefiniteInitializationPass()
        result = di_pass.run(mod)
        self.assertFalse(result.success)
        self.assertTrue(any("lida antes de ser inicializada" in e for e in result.errors))

    def test_system_capability_pass_rejects_unauthorized_call(self):
        fn = SIRFunction("user_fn", [], "void", is_system=False)
        b = fn.add_block("0")
        b.add(CallInst("privileged_kernel_op", [], is_system=True))
        b.add(ReturnInst())

        mod = SIRModule("test_safety")
        mod.add_function(fn)

        safety_pass = SystemCapabilitySafetyPass()
        result = safety_pass.run(mod)
        self.assertFalse(result.success)
        self.assertTrue(any("em função não-privilegiada" in e for e in result.errors))

    def test_dead_code_elimination_removes_unreachable_instructions(self):
        fn = SIRFunction("dead_fn", [], "void")
        b = fn.add_block("0")
        v = SIRValue("v", "i32")
        b.add(ReturnInst())
        b.add(AllocStackInst("dead_var", "i32", v))  # Inalcançável após return!

        mod = SIRModule("test_dce")
        mod.add_function(fn)

        dce = DeadCodeEliminationPass()
        dce.run(mod)
        self.assertEqual(len(b.instructions), 1)
        self.assertIsInstance(b.instructions[0], ReturnInst)


if __name__ == "__main__":
    unittest.main()
