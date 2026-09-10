"""Tests for Sotlas Low-Level Foundation Essentials.

Validates parsing, semantics, and compilation for:
- stdlib/foundation/engrave.sotlas (Non-allocating in-place stack formatter)
- stdlib/foundation/parcel.sotlas (Parcel with small inline storage)
- stdlib/system/ticker.sotlas (ClockPulse and monotonic_tick)
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema
from sotlas.codegen_c import CodegenC


class SotlasFoundationEssentialsTests(unittest.TestCase):

    def compile_file(self, path: Path) -> str:
        src = path.read_text(encoding="utf-8")
        tokens = Lexer(src, str(path)).tokenize()
        ast = Parser(tokens, str(path)).parse()
        Sema(ast, str(path), src).check()
        return CodegenC(ast).emit()

    def test_engrave_sotlas_compiles(self):
        p = ROOT / "stdlib" / "foundation" / "engrave.sotlas"
        self.assertTrue(p.exists(), f"File not found: {p}")
        c_code = self.compile_file(p)
        self.assertIn("engrave_u64_decimal", c_code)
        self.assertIn("engrave_u64_hex", c_code)
        self.assertIn("engrave_u64_bin", c_code)

    def test_parcel_sotlas_compiles(self):
        p = ROOT / "stdlib" / "foundation" / "parcel.sotlas"
        self.assertTrue(p.exists(), f"File not found: {p}")
        c_code = self.compile_file(p)
        self.assertIn("Parcel", c_code)
        self.assertIn("is_inline", c_code)
        self.assertIn("append", c_code)
        self.assertIn("deinit", c_code)

    def test_ticker_sotlas_compiles(self):
        p = ROOT / "stdlib" / "system" / "ticker.sotlas"
        self.assertTrue(p.exists(), f"File not found: {p}")
        c_code = self.compile_file(p)
        self.assertIn("ClockPulse", c_code)
        self.assertIn("monotonic_tick", c_code)
        self.assertIn("rdtsc", c_code)

    def test_fathom_sotlas_compiles(self):
        p = ROOT / "stdlib" / "foundation" / "fathom.sotlas"
        self.assertTrue(p.exists(), f"File not found: {p}")
        c_code = self.compile_file(p)
        self.assertIn("Fathom", c_code)
        self.assertIn("subfathom", c_code)
        self.assertIn("starts_with", c_code)


if __name__ == "__main__":
    unittest.main()
