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
        self.assertIn("sotlas", res.stdout.lower())
        self.assertIn("1.0.0", res.stdout)

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

    def test_native_compiler_stage2_self_compilation_fixed_point(self):
        from sotlas.bootstrap_pipeline import BOOTSTRAP_ENTRY, NATIVE_DRIVER_C
        from sotlas.llvm_toolchain import default_toolchain

        stage2_c = self.tmp_path / "stage2_compiler.c"
        # 1. Stage 1 (sotlas_native.exe) compila o código-fonte do próprio compilador em C
        res_st2 = subprocess.run(
            [str(self.native_compiler), str(BOOTSTRAP_ENTRY), "-o", str(stage2_c)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_st2.returncode, 0, f"Stage 1 falhou ao compilar o compilador:\n{res_st2.stderr}")
        self.assertTrue(stage2_c.is_file())

        # 2. Compila stage 2 para executável nativo
        driver_c = self.tmp_path / "stage2_driver.c"
        driver_c.write_text(NATIVE_DRIVER_C, encoding="utf-8")

        compiler_obj = self.tmp_path / "stage2_compiler.obj"
        driver_obj = self.tmp_path / "stage2_driver.obj"
        default_toolchain.compile_c_to_obj(stage2_c, compiler_obj, opt_level=2)
        default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=2)

        exe_suffix = ".exe" if os.name == "nt" else ""
        stage2_exe = self.tmp_path / f"sotlas_native_stage2{exe_suffix}"
        default_toolchain.link_native_binary([compiler_obj, driver_obj], stage2_exe)
        self.assertTrue(stage2_exe.is_file())

        # 3. Stage 2 executa --version
        res_ver = subprocess.run([str(stage2_exe), "--version"], capture_output=True, text=True)
        self.assertEqual(res_ver.returncode, 0)
        self.assertIn("sotlas", res_ver.stdout.lower())
        self.assertIn("1.0.0", res_ver.stdout)

        # 4. Stage 2 compila o compilador gerando stage3_compiler.c (Ponto Fixo / Fixed Point)
        stage3_c = self.tmp_path / "stage3_compiler.c"
        res_st3 = subprocess.run(
            [str(stage2_exe), str(BOOTSTRAP_ENTRY), "-o", str(stage3_c)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_st3.returncode, 0, f"Stage 2 falhou ao compilar Stage 3:\n{res_st3.stderr}")
        self.assertTrue(stage3_c.is_file())

        # Valida que Stage 2 e Stage 3 são rigorosamente equivalentes (Ponto Fixo)
        content_st2 = stage2_c.read_text(encoding="utf-8")
        content_st3 = stage3_c.read_text(encoding="utf-8")
        self.assertEqual(content_st2, content_st3, "Stage 2 e Stage 3 devem ser idênticos (ponto fixo atingido)")

        # 5. Valida que Stage 2 compila e roda um app Sotlas com sucesso
        app_file = ROOT / "bootstrap" / "sotlas" / "test_runtime_app.sotlas"
        run_res = subprocess.run([str(stage2_exe), "run", str(app_file)], capture_output=True, text=True)
        self.assertEqual(run_res.returncode, 0, f"Stage 2 run falhou:\n{run_res.stderr}")

    def test_native_compiler_compiles_modern_sotlas_constructs(self):
        code_file = self.tmp_path / "test_modern.sotlas"
        code_file.write_text("""module test::modern;

pub sole struct Packet {
    pub id: u64;
    pub payload: u32;
}

pub fn main() -> i32 {
    let mut p: Packet = 0;
    p.id = 42;
    p.payload = 100;
    let q: Packet = handover p;

    let sz: usize = span_of::<Packet>();
    let al: usize = align_of::<Packet>();
    let off: usize = field_offset!(Packet, payload);

    clinch {
        let mut x: u32 = 10;
        x = x + 1;
    } revert {
    }

    if q.id == 42 && sz >= 12 && al >= 4 && off >= 8 {
        return 0;
    }
    return 1;
}
""", encoding="utf-8")

        exe_suffix = ".exe" if os.name == "nt" else ""
        out_exe = self.tmp_path / f"test_modern{exe_suffix}"

        res = subprocess.run(
            [str(self.native_compiler), str(code_file), "-o", str(out_exe)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Falha na compilação nativa de construções modernas:\n{res.stderr}")
        self.assertTrue(out_exe.is_file())

        run_res = subprocess.run([str(out_exe)], capture_output=True, text=True)
        self.assertEqual(run_res.returncode, 0, f"Execução de construções modernas retornou erro: {run_res.returncode}")

    def test_native_compiler_compiles_discern_probe_and_pulse(self):
        code_file = self.tmp_path / "test_discern_probe.sotlas"
        code_file.write_text("""module test::discern_probe_app;

pub enum Mode {
    Idle,
    Active,
    Halt
}

pub fn classify_mode(m: Mode) -> i32 {
    discern m {
        case .Idle => {
            return 10;
        }
        case .Active => {
            return 20;
        }
        case .Halt => {
            return 30;
        }
    }
    return 0;
}

pub fn check_levels(v: i32) -> i32 {
    discern v {
        case 1 => {
            return 100;
        }
        case 2 => {
            return 200;
        }
        case else => {
            return 999;
        }
    }
    return 0;
}

pub fn main() -> i32 {
    pulse;

    let m: Mode = Mode::Active;
    let score: i32 = classify_mode(m);
    probe score == 20;

    let lvl: i32 = check_levels(2);
    probe lvl == 200;

    let def_lvl: i32 = check_levels(99);
    probe def_lvl == 999;

    let mut sum: i32 = 0;
    for mut i in 0..5 {
        if i == 2 {
            continue;
        }
        sum = sum + (i as i32);
    }
    probe sum == 8;

    return 0;
}
""", encoding="utf-8")

        exe_suffix = ".exe" if os.name == "nt" else ""
        out_exe = self.tmp_path / f"test_discern_probe{exe_suffix}"

        res = subprocess.run(
            [str(self.native_compiler), str(code_file), "-o", str(out_exe)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Falha na compilação nativa de discern, probe e pulse:\n{res.stderr}")
        self.assertTrue(out_exe.is_file())

        run_res = subprocess.run([str(out_exe)], capture_output=True, text=True)
        self.assertEqual(run_res.returncode, 0, f"Execução de discern/probe retornou erro: {run_res.returncode}")

    def test_native_compiler_compiles_bit_accessors_and_topology_pointers(self):
        code_file = self.tmp_path / "test_hardware_bits.sotlas"
        code_file.write_text("""module test::hardware_bits;

pub fn read_io(ptr: *rawphys u32) -> u32 {
    unsafe {
        return *ptr;
    }
}

pub fn main() -> i32 {
    let reg: u64 = 0x123456789ABCDEF0;

    let bit4: u64 = reg.notch[4];
    probe bit4 == 1;

    let bit0: u64 = reg.notch[0];
    probe bit0 == 0;

    let nibble: u64 = reg.slit[4..7];
    probe nibble == 15;

    let swapped: u64 = reg.strand;
    probe swapped.strand == reg;

    let mut val: u32 = 42;
    let ptr: *rawphys u32 = &mut val as *rawphys u32;
    let read_val: u32 = read_io(ptr);
    probe read_val == 42;

    return 0;
}
""", encoding="utf-8")

        exe_suffix = ".exe" if os.name == "nt" else ""
        out_exe = self.tmp_path / f"test_hardware_bits{exe_suffix}"

        res = subprocess.run(
            [str(self.native_compiler), str(code_file), "-o", str(out_exe)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Falha na compilação nativa de acessores de bits e topologia:\n{res.stderr}")
        self.assertTrue(out_exe.is_file())

        run_res = subprocess.run([str(out_exe)], capture_output=True, text=True)
        self.assertEqual(run_res.returncode, 0, f"Execução de acessores de bits retornou erro: {run_res.returncode}")

    def test_native_compiler_test_subcommand(self):
        """Valida a funcionalidade completa do subcomando 'test' do compilador nativo."""
        # 1. Executa a suíte inteira de testes nativos
        res = subprocess.run(
            [str(self.native_compiler), "test", "tests/native"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"sotlas_native test falhou:\n{res.stdout}\n{res.stderr}")
        self.assertIn("[PASS]", res.stdout)
        self.assertIn("aprovados, 0 falhas", res.stdout)
        self.assertIn("Todos os testes nativos passaram com sucesso", res.stdout)

        # 2. Executa um arquivo de teste individual
        res_single = subprocess.run(
            [str(self.native_compiler), "test", "tests/native/test_primitives.sotlas"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_single.returncode, 0)
        self.assertIn("[PASS]", res_single.stdout)
        self.assertIn("test_primitives.sotlas", res_single.stdout)

    def test_native_compiler_package_manager_subcommands(self):
        """Valida os subcomandos 'new', 'add' e 'build' nativos (Zero-Python)."""
        pkg_dir = self.tmp_path / "my_native_app"

        # 1. new
        res_new = subprocess.run(
            [str(self.native_compiler), "new", str(pkg_dir)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_new.returncode, 0, f"sotlas_native new falhou: {res_new.stderr}")
        self.assertTrue((pkg_dir / "Sotlas.toml").is_file())
        self.assertTrue((pkg_dir / "src" / "main.sotlas").is_file())

        # 2. add
        res_add = subprocess.run(
            [str(self.native_compiler), "add", "sotlas-foundation", "--version", "^0.3.0", "--path", str(pkg_dir)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_add.returncode, 0, f"sotlas_native add falhou: {res_add.stderr}")
        manifest_text = (pkg_dir / "Sotlas.toml").read_text(encoding="utf-8")
        self.assertIn("sotlas-foundation", manifest_text)
        self.assertIn("^0.3.0", manifest_text)

        # 3. build
        res_build = subprocess.run(
            [str(self.native_compiler), "build", "--path", str(pkg_dir)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_build.returncode, 0, f"sotlas_native build falhou: {res_build.stderr}")
        self.assertTrue((pkg_dir / "build" / "my_native_app.c").is_file())
        exe_suffix = ".exe" if os.name == "nt" else ".bin"
        out_bin = pkg_dir / "build" / f"my_native_app{exe_suffix}"
        self.assertTrue(out_bin.is_file())

        # 4. Executa o executável gerado
        run_res = subprocess.run([str(out_bin)])
        self.assertEqual(run_res.returncode, 0)

    def test_native_compiler_fmt_and_lint_subcommands(self):
        """Valida os subcomandos 'fmt' e 'lint' nativos (Zero-Python)."""
        code_file = self.tmp_path / "messy_code.sotlas"
        code_file.write_text("""module test::messy;

struct bad_name {
    x:u32
}

pub fn BadFunction(a:u32,b:u32)->u32 {
\treturn a+b;
}
""", encoding="utf-8")

        # 1. Lint detecta avisos
        res_lint = subprocess.run(
            [str(self.native_compiler), "lint", str(code_file)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_lint.returncode, 1)
        self.assertIn("naming-type-pascal-case", res_lint.stdout)
        self.assertIn("naming-fn-snake-case", res_lint.stdout)
        self.assertIn("no-tabs", res_lint.stdout)

        # 2. fmt --check detecta necessidade de formatação
        res_check = subprocess.run(
            [str(self.native_compiler), "fmt", str(code_file), "--check"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_check.returncode, 1)
        self.assertIn("formatacao necessaria", res_check.stdout)

        # 3. fmt formata o arquivo
        res_fmt = subprocess.run(
            [str(self.native_compiler), "fmt", str(code_file)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res_fmt.returncode, 0)
        formatted_src = code_file.read_text(encoding="utf-8")
        self.assertIn("-> u32", formatted_src)
        self.assertIn("x: u32", formatted_src)


if __name__ == "__main__":
    unittest.main()


