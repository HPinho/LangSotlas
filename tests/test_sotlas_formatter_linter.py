"""Testes unitários para o formatador, linter e gerador de documentação."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.formatter import format_code
from sotlas.linter import lint_source
from sotlas.docgen import extract_docs, generate_markdown


class SotlasFormatterLinterDocTests(unittest.TestCase):
    def test_formatter_normalizes_indentation_and_operators(self):
        ugly_code = """module foo;
fn calc(a:u32,b:u32)->u32{
let x=a+b;
return x;
}"""
        formatted = format_code(ugly_code)
        self.assertIn("fn calc(a: u32, b: u32) -> u32", formatted)
        self.assertIn("    let x = a + b;", formatted)
        self.assertIn("    return x;", formatted)

    def test_linter_detects_naming_conventions_and_tabs(self):
        bad_code = """
module bad_style;

struct my_point {
\tx: u32;
}

fn MyFunction() -> u32 {
    return 42;
}
"""
        warnings = lint_source(bad_code, "test.sotlas")
        rule_ids = [w.rule for w in warnings]
        self.assertIn("naming-fn-snake-case", rule_ids)
        self.assertIn("naming-type-pascal-case", rule_ids)
        self.assertIn("no-tabs", rule_ids)

    def test_docgen_extracts_docstrings_and_signatures(self):
        documented_code = """
/// Módulo de teste de documentação
module math::utils;

/// Estrutura para representar pontos 2D
pub struct Point {
    pub x: i32;
    pub y: i32;
}

/// Realiza a soma de dois números inteiros
pub fn add(a: u32, b: u32) -> u32 {
    return a + b;
}
"""
        items = extract_docs(documented_code)
        self.assertEqual(len(items), 3)

        md = generate_markdown(items, "API Math Utils")
        self.assertIn("# API Math Utils", md)
        self.assertIn("Módulo de teste de documentação", md)
        self.assertIn("Estrutura para representar pontos 2D", md)
        self.assertIn("Realiza a soma de dois números inteiros", md)


if __name__ == "__main__":
    unittest.main()
