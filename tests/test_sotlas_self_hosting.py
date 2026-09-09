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

    def test_native_compiler_compiles_and_runs_runtime_app(self):
        app_file = self.tmp_path / "test_runtime_app.sotlas"
        app_file.write_text("""module test::runtime_app;

struct Rect {
    width: i32,
    height: i32
}

pub fn area(r: Rect) -> i32 {
    return r.width * r.height;
}

pub fn compute_sum(n: i32) -> i32 {
    let mut sum: i32 = 0;
    let mut i: i32 = 1;
    while i <= n {
        sum = sum + i;
        i = i + 1;
    }
    return sum;
}

pub fn main() -> i32 {
    let mut r: Rect = 0;
    r.width = 15;
    r.height = 8;
    let a: i32 = area(r);
    let s: i32 = compute_sum(10);
    if a == 120 && s == 55 {
        return 0;
    } else {
        return 1;
    }
}
""", encoding="utf-8")

        exe_suffix = ".exe" if os.name == "nt" else ""
        out_exe = self.tmp_path / f"test_runtime_app{exe_suffix}"

        # Compila diretamente para binário executável via sotlas_native
        res = subprocess.run(
            [str(self.native_compiler), str(app_file), "-o", str(out_exe)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Falha ao compilar runtime app:\n{res.stderr}")
        self.assertTrue(out_exe.is_file())

        # Executa o aplicativo compilado e verifica retorno 0 (validação completa)
        run_res = subprocess.run([str(out_exe)], capture_output=True, text=True)
        self.assertEqual(run_res.returncode, 0, f"O aplicativo de runtime retornou erro {run_res.returncode}")

    def test_native_compiler_run_subcommand(self):
        st_file = self.tmp_path / "quick_run.sotlas"
        st_file.write_text("""module test::quick;
pub fn main() -> i32 {
    let mut a: i32 = 40;
    let mut b: i32 = 2;
    if a + b == 42 {
        return 0;
    } else {
        return 1;
    }
}
""", encoding="utf-8")

        res = subprocess.run(
            [str(self.native_compiler), "run", str(st_file)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"sotlas_native run deve retornar 0:\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
