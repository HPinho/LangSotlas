"""Testes unitários para Concorrência Segura, pulse, probe e Enclave em Sotlas."""
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "compiler"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema
from sotlas.codegen_c import CodegenC
from sotlas.codegen_wasm import CodegenWasm


class TestSotlasSyncEnclave(unittest.TestCase):
    def test_pulse_statement_and_expression(self):
        source = """\
module test::pulse;

pub fn barrier() {
    pulse;
    pulse();
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>", source).check()
        c_code = CodegenC(ast).emit()
        self.assertIn("mfence", c_code)

    def test_probe_assertion_statement(self):
        source = """\
module test::probe;

pub fn check_val(x: i64) {
    probe x > 0, "x deve ser positivo";
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>", source).check()
        c_code = CodegenC(ast).emit()
        self.assertIn("probe:", c_code)
        self.assertIn("__builtin_trap()", c_code)

    def test_sync_system_module_compiles(self):
        sync_file = _ROOT / "stdlib" / "system" / "sync.sotlas"
        text = sync_file.read_text(encoding="utf-8")
        tokens = Lexer(text, str(sync_file)).tokenize()
        ast = Parser(tokens, str(sync_file)).parse()
        Sema(ast, str(sync_file), text).check()
        c_code = CodegenC(ast).emit()
        self.assertIn("struct SpinLock", c_code)
        self.assertIn("struct Enclave", c_code)


if __name__ == "__main__":
    unittest.main()
