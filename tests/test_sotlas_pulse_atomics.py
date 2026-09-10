import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema
from sotlas.codegen_c import CodegenC


class SotlasPulseAndShieldTests(unittest.TestCase):

    def compile_src(self, src: str) -> str:
        tokens = Lexer(src, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>").check()
        return CodegenC(ast).emit()

    def test_pulse_stdlib_parses_and_compiles(self):
        pulse_path = ROOT / "stdlib" / "system" / "pulse.sotlas"
        src = pulse_path.read_text(encoding="utf-8")
        c = self.compile_src(src)
        self.assertIn("__atomic_load_u32", c)
        self.assertIn("__atomic_cmpxchg_u32", c)
        self.assertIn("__atomic_cmpxchg_u64", c)

    def test_shield_clinch_and_guard_in_sync_module(self):
        sync_path = ROOT / "stdlib" / "system" / "sync.sotlas"
        src = sync_path.read_text(encoding="utf-8")
        c = self.compile_src(src)
        self.assertIn("ShieldClinch", c)
        self.assertIn("ShieldGuard", c)
        self.assertIn("__irq_save_disable", c)
        self.assertIn("__irq_restore", c)

    def test_wire_stdlib_parses_and_compiles(self):
        wire_path = ROOT / "stdlib" / "system" / "wire.sotlas"
        src = wire_path.read_text(encoding="utf-8")
        c = self.compile_src(src)
        self.assertIn("Wire", c)

    def test_fathom_stdlib_parses_and_compiles(self):
        fathom_path = ROOT / "stdlib" / "core" / "fathom.sotlas"
        src = fathom_path.read_text(encoding="utf-8")
        c = self.compile_src(src)
        self.assertIn("Fathom", c)

    def test_clinch_nesting_emits_unique_flags_and_safe_restore(self):
        src = """module test::nesting;
        @system
        pub fn nested_critical_sections() {
            clinch {
                let x: u32 = 1;
                clinch {
                    let y: u32 = 2;
                }
            }
        }"""
        c = self.compile_src(src)
        self.assertIn("_sotlas_clinch_flags_0", c)
        self.assertIn("_sotlas_clinch_flags_1", c)
        self.assertIn("__irq_save_disable", c)
        self.assertIn("__irq_restore", c)


if __name__ == "__main__":
    unittest.main()
