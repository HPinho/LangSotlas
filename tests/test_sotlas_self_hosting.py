"""Testes para o pipeline de auto-hospedagem (self-hosting) e compilador nativo de Sotlas."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.bootstrap_pipeline import build_self_hosted_compiler, verify_self_hosted_compiler


class TestSotlasSelfHosting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.tmp_path = Path(cls.tmpdir.name)
        exe_suffix = ".exe" if os.name == "nt" else ""
        cls.native_compiler = cls.tmp_path / f"sotlas_native{exe_suffix}"
        # Compila uma única vez para toda a classe de teste
        build_self_hosted_compiler(cls.native_compiler, verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmpdir.cleanup()

    def test_native_compiler_binary_exists_and_is_executable(self):
        self.assertTrue(self.native_compiler.is_file())
        self.assertGreater(self.native_compiler.stat().st_size, 50000)

    def test_native_compiler_version_flag(self):
        res = subprocess.run([str(self.native_compiler), "--version"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Sotlas Native Compiler", res.stdout)
        self.assertIn("Self-Hosted", res.stdout)

    def test_native_compiler_verify_cycle(self):
        ok = verify_self_hosted_compiler(self.native_compiler)
        self.assertTrue(ok, "O ciclo de validação do compilador auto-hospedado deve passar")

    def test_native_compiler_compiles_custom_sotlas_code(self):
        st_file = self.tmp_path / "custom_module.sotlas"
        st_file.write_text("""module test::kernel_math;
pub fn square(n: u32) -> u32 {
    let result: u32 = n * n;
    return result;
}
""", encoding="utf-8")

        out_c = self.tmp_path / "custom_module.c"
        res = subprocess.run(
            [str(self.native_compiler), str(st_file), "-o", str(out_c)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(out_c.is_file())
        c_code = out_c.read_text(encoding="utf-8")
        self.assertIn("uint32_t", c_code)
        self.assertIn("square", c_code)
        self.assertIn("return result", c_code)


if __name__ == "__main__":
    unittest.main()
