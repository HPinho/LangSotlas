"""Testes unitários para a infraestrutura de self-hosting e runtime standalone."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))

from sotlas import compile_source


class SotlasBootstrapSelfhostTests(unittest.TestCase):
    def test_bootstrap_lexer_in_sotlas_compiles(self):
        bootstrap_path = ROOT / "bootstrap" / "sotlas_bootstrap.sotlas"
        self.assertTrue(bootstrap_path.exists())
        text = bootstrap_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(bootstrap_path))

        self.assertIn("TokenKind", c_code)
        self.assertIn("Span", c_code)
        self.assertIn("SotlasLexer", c_code)
        self.assertIn("next_token", c_code)
        self.assertIn("skip_whitespace", c_code)

    def test_libsotlas_rt_headers_and_sources_exist(self):
        rt_header = ROOT / "runtime" / "libsotlas_rt.h"
        rt_source = ROOT / "runtime" / "libsotlas_rt.c"
        self.assertTrue(rt_header.exists())
        self.assertTrue(rt_source.exists())

        header_content = rt_header.read_text(encoding="utf-8")
        self.assertIn("sotlas_rt_alloc", header_content)
        self.assertIn("sotlas_rt_arc_retain", header_content)
        self.assertIn("sotlas_rt_panic", header_content)


if __name__ == "__main__":
    unittest.main()
