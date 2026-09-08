"""Testes unitários para Pattern Matching Exaustivo com discern em Sotlas."""
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "compiler"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError
from sotlas.codegen_c import CodegenC
from sotlas.codegen_wasm import CodegenWasm


class TestSotlasDiscernMatching(unittest.TestCase):
    def test_discern_valid_exhaustive(self):
        source = """\
module test::discern_ok;

pub enum State {
    Init,
    Running,
    Stopped,
}

pub fn check_state(s: State) -> i64 {
    discern s {
        case .Init => {
            return 1;
        }
        case .Running => {
            return 2;
        }
        case .Stopped => {
            return 3;
        }
    }
    return 0;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>", source).check()
        c_code = CodegenC(ast).emit()
        self.assertIn("switch (s)", c_code)
        self.assertIn("case Init:", c_code)
        self.assertIn("case Running:", c_code)
        self.assertIn("case Stopped:", c_code)

    def test_discern_with_default_else(self):
        source = """\
module test::discern_else;

pub enum Color {
    Red,
    Green,
    Blue,
}

pub fn check_color(c: Color) -> i64 {
    discern c {
        case .Red => {
            return 1;
        }
        case else => {
            return 0;
        }
    }
    return 0;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>", source).check()
        c_code = CodegenC(ast).emit()
        self.assertIn("default:", c_code)

    def test_discern_non_exhaustive_error(self):
        source = """\
module test::discern_non_exhaustive;

pub enum Traffic {
    Red,
    Yellow,
    Green,
}

pub fn check_traffic(t: Traffic) -> i64 {
    discern t {
        case .Red => {
            return 1;
        }
    }
    return 0;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        with self.assertRaises(SotlasSemaError) as ctx:
            Sema(ast, "<test>", source).check()
        self.assertIn("discern não exaustivo", str(ctx.exception))
        self.assertIn("Green", str(ctx.exception))
        self.assertIn("Yellow", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
