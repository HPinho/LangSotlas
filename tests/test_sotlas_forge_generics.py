"""Testes unitários para Generics Monomorfizados com forge<T> em Sotlas."""
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


class TestSotlasForgeGenerics(unittest.TestCase):
    def test_generic_struct_declaration(self):
        source = """\
module test::generics;

pub struct Container forge<T> {
    pub item: T;

    pub fn new(val: T) -> Container forge<T> {
        return Container { item: val };
    }
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        self.assertEqual(len(ast.decls), 1)
        struct_decl = ast.decls[0]
        self.assertEqual(struct_decl.name, "Container")
        self.assertEqual(struct_decl.generics, ["T"])

        Sema(ast, "<test>", source).check()
        c_code = CodegenC(ast).emit()
        self.assertIn("struct Container", c_code)

    def test_generic_type_usage_monomorphization(self):
        source = """\
module test::monomorph;

pub struct Pair forge<A, B> {
    pub first: A;
    pub second: B;
}

pub fn make_pair() -> Pair forge<u32, i64> {
    return Pair { first: 10, second: 20 };
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>", source).check()
        c_code = CodegenC(ast).emit()
        self.assertIn("Pair_uint32_t_int64_t", c_code)


if __name__ == "__main__":
    unittest.main()
