"""Tests for the Sotlas Flight Diagnostics & Redress Engine."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.diagnostics import SourceSpan, Redress, FlightDiagnostic, apply_redresses
from sotlas.linter import lint_source_diagnostics, lint_and_fix_source, lint_source


class TestSotlasDiagnosticsAndRedress(unittest.TestCase):

    def test_apply_single_redress(self):
        source = "let a = 10;\nlet b = 20;"
        span = SourceSpan(
            file="test.sotlas",
            start_line=1,
            start_col=5,
            start_offset=4,
            end_line=1,
            end_col=6,
            end_offset=5
        )
        redress = Redress(span=span, replacement="x", description="rename a to x")
        fixed = apply_redresses(source, [redress])
        self.assertEqual(fixed, "let x = 10;\nlet b = 20;")

    def test_apply_multiple_redresses_reverse_order(self):
        source = "fn Foo() {\n\treturn 1;\n}"
        span_name = SourceSpan(
            file="test.sotlas",
            start_line=1,
            start_col=4,
            start_offset=3,
            end_line=1,
            end_col=7,
            end_offset=6
        )
        span_tab = SourceSpan(
            file="test.sotlas",
            start_line=2,
            start_col=1,
            start_offset=11,
            end_line=2,
            end_col=2,
            end_offset=12
        )
        r1 = Redress(span=span_name, replacement="foo", description="snake_case")
        r2 = Redress(span=span_tab, replacement="    ", description="spaces")

        fixed = apply_redresses(source, [r1, r2])
        self.assertEqual(fixed, "fn foo() {\n    return 1;\n}")

    def test_linter_diagnostics_with_redress(self):
        source = "fn MyFunction() {\n\tlet x = 1;\n}\nstruct point {\n    x: i32;\n}\n"
        diagnostics = lint_source_diagnostics(source, "module.sotlas")
        self.assertTrue(len(diagnostics) >= 3)

        codes = [d.code for d in diagnostics]
        self.assertIn("naming-fn-snake-case", codes)
        self.assertIn("no-tabs", codes)
        self.assertIn("naming-type-pascal-case", codes)

        for d in diagnostics:
            self.assertTrue(len(d.redresses) > 0)

    def test_linter_autofix(self):
        source = "fn ProcessData() {\n\treturn 42;\n}\n"
        fixed, diags = lint_and_fix_source(source, "example.sotlas")
        self.assertIn("fn process_data()", fixed)
        self.assertNotIn("\t", fixed)
        self.assertIn("    return 42;", fixed)

    def test_backward_compatibility_lint_warnings(self):
        source = "fn Test() {\n\treturn 0;\n}\n"
        warnings = lint_source(source, "legacy.sotlas")
        self.assertTrue(len(warnings) >= 2)
        self.assertIsNotNone(warnings[0].diagnostic)


if __name__ == "__main__":
    unittest.main()
