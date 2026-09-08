"""Testes de emissão direta de código objeto (.obj / .o) e executáveis nativos via LLVM / LLD."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.llvm_toolchain import LLVMToolchain, default_toolchain


class TestSotlasLLVMDirectEmission(unittest.TestCase):
    def setUp(self):
        self.toolchain = default_toolchain
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_llvm_toolchain_detected(self):
        self.assertTrue(self.toolchain.is_available(), "LLVM Clang deve ser detectado no ambiente")
        version = self.toolchain.get_version()
        self.assertIn("clang version", version)
        clang_path = self.toolchain.find_tool("clang")
        self.assertIsNotNone(clang_path)
        self.assertTrue(clang_path.exists())

    def test_compile_llvm_ir_to_native_obj(self):
        ir_code = """
target triple = "x86_64-pc-windows-msvc"

define i32 @add_numbers(i32 %a, i32 %b) {
entry:
    %res = add i32 %a, %b
    ret i32 %res
}
"""
        obj_file = self.tmp_path / "math.obj"
        res_obj = self.toolchain.compile_llvm_ir_to_obj(ir_code, obj_file, opt_level=2)
        self.assertTrue(res_obj.is_file())
        self.assertGreater(res_obj.stat().st_size, 0)

    def test_link_native_executable_and_execute(self):
        ir_code = """
target triple = "x86_64-pc-windows-msvc"

define i32 @main() {
entry:
    ret i32 55
}
"""
        obj_file = self.tmp_path / "main.obj"
        exe_file = self.tmp_path / "main.exe"

        self.toolchain.compile_llvm_ir_to_obj(ir_code, obj_file)
        self.toolchain.link_native_binary([obj_file], exe_file)

        self.assertTrue(exe_file.is_file())
        run_res = subprocess.run([str(exe_file)])
        self.assertEqual(run_res.returncode, 55)

    def test_compile_sotlas_source_to_native_obj(self):
        source = """module test::obj_demo;
pub fn compute(x: u32) -> u32 {
    let factor: u32 = 4;
    return x * factor;
}
"""
        obj_file = self.tmp_path / "compute.obj"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::obj_demo",
            obj_file,
            emit_type="obj",
            backend="c11"
        )
        self.assertTrue(res.is_file())
        self.assertGreater(res.stat().st_size, 100)

    def test_compile_sotlas_source_to_native_exe_and_run(self):
        source = """module test::exe_demo;
pub fn main() -> i32 {
    let mut a: i32 = 20;
    let b: i32 = 22;
    return a + b;
}
"""
        exe_file = self.tmp_path / "test_app.exe"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::exe_demo",
            exe_file,
            emit_type="exe",
            backend="c11"
        )
        self.assertTrue(res.is_file())
        run_res = subprocess.run([str(res)])
        self.assertEqual(run_res.returncode, 42)

    def test_compile_sotlas_source_to_llvm_ir(self):
        source = """module test::ir_demo;
pub fn answer() -> i32 {
    return 42;
}
"""
        ll_file = self.tmp_path / "answer.ll"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::ir_demo",
            ll_file,
            emit_type="llvm",
            backend="llvm"
        )
        self.assertTrue(res.is_file())
        content = res.read_text(encoding="utf-8")
        self.assertIn("ModuleID", content)
        self.assertIn("@answer", content)


if __name__ == "__main__":
    unittest.main()
