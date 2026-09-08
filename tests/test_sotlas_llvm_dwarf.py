"""Testes unitários para a geração de metadados DWARF no backend LLVM IR."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.codegen_llvm import CodegenLLVM
from sotlas.sir import SIRGenerator
from sotlas_compile import bootstrap as production_frontend


class SotlasLLVMDWARFTests(unittest.TestCase):
    def test_emit_llvm_with_dwarf_debug_metadata(self):
        source = """
module debug::test;

pub fn add(a: u32, b: u32) -> u32 {
    return a + b;
}
"""
        ast_mod = production_frontend.parse(source, "<debug_test>")
        gen = SIRGenerator()
        sir_mod = gen.generate_from_ast(ast_mod)

        # 1. Sem debug
        codegen_no_dbg = CodegenLLVM(sir_mod, emit_debug=False)
        ir_no_dbg = codegen_no_dbg.emit()
        self.assertNotIn("!llvm.dbg.cu", ir_no_dbg)
        self.assertNotIn("!DISubprogram", ir_no_dbg)

        # 2. Com metadados DWARF
        codegen_dbg = CodegenLLVM(sir_mod, emit_debug=True)
        ir_dbg = codegen_dbg.emit()

        self.assertIn("!llvm.dbg.cu = !{!0}", ir_dbg)
        self.assertIn("!llvm.module.flags", ir_dbg)
        self.assertIn("distinct !DICompileUnit", ir_dbg)
        self.assertIn("distinct !DISubprogram(name: \"add\"", ir_dbg)
        self.assertIn("!DILocation", ir_dbg)
        self.assertIn("!dbg !", ir_dbg)


if __name__ == "__main__":
    unittest.main()
