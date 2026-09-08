"""Testes unitários para o Backend WebAssembly Direto (Bypass de C11/C99)."""
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "compiler"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema
from sotlas.codegen_wasm import CodegenWasm


class TestSotlasWasmBackend(unittest.TestCase):
    def test_direct_wasm_math_function(self):
        source = """\
module test::wasm_math;

pub fn add(a: i32, b: i32) -> i32 {
    return a + b;
}

pub fn multiply(x: i32, y: i32) -> i32 {
    return x * y;
}
"""
        tokens = Lexer(source, "<wasm_test>").tokenize()
        ast = Parser(tokens, "<wasm_test>").parse()
        Sema(ast, "<wasm_test>", source).check()

        wasm_gen = CodegenWasm(ast)
        wat = wasm_gen.emit_wat()

        self.assertIn("(module", wat)
        self.assertIn('(func $add (export "add") (param $a i32) (param $b i32) (result i32)', wat)
        self.assertIn("i32.add", wat)
        self.assertIn('(func $multiply (export "multiply") (param $x i32) (param $y i32) (result i32)', wat)
        self.assertIn("i32.mul", wat)

    def test_direct_wasm_discern_and_probe(self):
        source = """\
module test::wasm_discern;

pub fn check_even(val: i32) -> i32 {
    probe val >= 0;
    discern val {
        case 0 => {
            return 100;
        }
        case else => {
            return 200;
        }
    }
    return 0;
}
"""
        tokens = Lexer(source, "<wasm_test>").tokenize()
        ast = Parser(tokens, "<wasm_test>").parse()
        Sema(ast, "<wasm_test>", source).check()

        wasm_gen = CodegenWasm(ast)
        wat = wasm_gen.emit_wat()

        self.assertIn(";; discern", wat)
        self.assertIn("call $panic", wat)
        self.assertIn("return", wat)


if __name__ == "__main__":
    unittest.main()
