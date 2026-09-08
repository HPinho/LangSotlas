#!/usr/bin/env python3
"""Testes de integridade da SOTLAS UI: Render Tree, RenderNode e Materiais (Etapa 2)."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL_ROOT = ROOT if (ROOT / "kernel").is_dir() else (ROOT.parent / "projeto-bkn")
SPEC = importlib.util.spec_from_file_location("compiler", ROOT / "tools" / "sotlas_compile" / "compiler.py")
assert SPEC is not None and SPEC.loader is not None
sotlas_compile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sotlas_compile)


class SotlasUIRenderTreeTests(unittest.TestCase):
    def test_sotlas_ui_module_parses_cleanly(self):
        source_path = KERNEL_ROOT / "kernel" / "src" / "sotlas_ui.sotlas"
        if not source_path.is_file():
            self.skipTest(f"Kernel source not found at {source_path}")
        self.assertTrue(source_path.is_file())
        source = source_path.read_text(encoding="utf-8")
        ast = sotlas_compile.parse_module_ast(source)
        self.assertEqual(ast.name, "kernel::sotlas_ui")

        # Verifica estruturas da SOTLAS UI e Layout Engine
        struct_names = {s.name for s in ast.structs}
        for expected in ("Material", "RenderNode", "RenderTree", "LayoutParams"):
            self.assertIn(expected, struct_names, f"Estrutura {expected} ausente no AST de sotlas_ui")

        # Verifica funções e métodos da RenderTree, Materiais e Layout
        fn_names = {f.name for f in ast.functions}
        for expected_fn in (
            "material_solid", "material_glass", "material_acrylic", "material_accent",
            "layout_none", "layout_vstack", "layout_hstack",
            "RenderTree_init", "RenderTree_clear", "RenderTree_alloc_node",
            "RenderTree_add_child", "RenderTree_set_material", "RenderTree_set_layout",
            "RenderTree_set_text", "RenderTree_set_icon",
            "RenderTree_measure_node", "RenderTree_layout_node", "RenderTree_layout",
            "RenderTree_draw_node", "RenderTree_draw"
        ):
            self.assertIn(expected_fn, fn_names, f"Função {expected_fn} ausente no AST de sotlas_ui")

    def test_compositor_integrates_render_tree(self):
        compositor_path = KERNEL_ROOT / "kernel" / "src" / "desktop_compositor.sotlas"
        if not compositor_path.is_file():
            self.skipTest(f"Kernel source not found at {compositor_path}")
        compositor_source = compositor_path.read_text(encoding="utf-8")
        self.assertIn("import kernel::sotlas_ui::*;", compositor_source)
        self.assertIn("ROOT_RENDER_TREE: RenderTree", compositor_source)
        self.assertIn("pub fn compositor_get_render_tree() -> *mut RenderTree", compositor_source)
        self.assertIn("RenderTree_init(&mut ROOT_RENDER_TREE);", compositor_source)

    def test_main_imports_sotlas_ui(self):
        main_path = KERNEL_ROOT / "kernel" / "src" / "main.sotlas"
        if not main_path.is_file():
            self.skipTest(f"Kernel source not found at {main_path}")
        main_source = main_path.read_text(encoding="utf-8")
        self.assertIn("import kernel::sotlas_ui::*;", main_source)

    def test_app_about_uses_sotlas_ui_and_zero_gfx(self):
        about_path = KERNEL_ROOT / "kernel" / "src" / "app_about.sotlas"
        if not about_path.is_file():
            self.skipTest(f"Kernel source not found at {about_path}")
        about_source = about_path.read_text(encoding="utf-8")
        self.assertIn("import kernel::sotlas_ui::*;", about_source)
        self.assertIn("import kernel::sotlas_graphics::*;", about_source)
        self.assertNotIn("gfx_", about_source)
        self.assertIn("RenderTree_layout(", about_source)
        self.assertIn("RenderTree_draw(", about_source)


if __name__ == "__main__":
    unittest.main()
