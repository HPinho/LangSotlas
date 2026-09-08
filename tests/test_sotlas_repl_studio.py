"""Testes unitários para o REPL e o Sotlas Studio."""
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "compiler"))

from sotlas.repl import SotlasRepl
from sotlas.studio import StudioHandler


class TestSotlasReplStudio(unittest.TestCase):
    def test_repl_eval_expression(self):
        repl = SotlasRepl()
        # Não deve levantar exceções
        repl._eval("let x: i64 = 42;")
        self.assertEqual(len(repl.session_decls), 1)

    def test_studio_compile_handler_all_backends(self):
        handler = StudioHandler.__new__(StudioHandler)
        source = """\
module test::studio;

pub fn calculate() -> i64 {
    let mut x: i64 = 10;
    x = x + 32;
    probe x == 42;
    return x;
}
"""
        res = handler.compile_source_all_backends(source)
        self.assertEqual(res["status"], "ok")
        self.assertIn("Compilado com Sucesso", res["output"])
        self.assertIn("(module", res["wasm"])
        self.assertIn("calculate", res["c11"])
        self.assertIn("SourceFile", res["ast"])

    def test_studio_static_assets_exist(self):
        html_file = _ROOT / "web" / "studio" / "index.html"
        self.assertTrue(html_file.exists())
        content = html_file.read_text(encoding="utf-8")
        self.assertIn("SOTLAS STUDIO", content)
        self.assertIn("forge", content)
        self.assertIn("discern", content)


if __name__ == "__main__":
    unittest.main()
