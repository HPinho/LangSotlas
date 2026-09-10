"""Testes para defer, RAII deinit, operador de try ? e loops for..in."""
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas_compile import bootstrap
from sotlas.llvm_toolchain import default_toolchain


class TestSotlasDeferRaiiErgonomics(unittest.TestCase):
    def _compile_and_run(self, source: str) -> int:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            c_file = tmp / "app.c"
            obj_file = tmp / "app.obj"
            exe_file = tmp / "app.exe"

            c_code = bootstrap.compile_source(source)
            c_file.write_text(c_code, encoding="utf-8")

            default_toolchain.compile_c_to_obj(c_file, obj_file, opt_level=2)
            default_toolchain.link_native_binary([obj_file], exe_file)

            res = subprocess.run([str(exe_file)], capture_output=True, text=True)
            return res.returncode

    def test_defer_lifo_execution_order(self):
        source = """module test::defer_lifo;

static mut g_order: u32 = 0;

pub fn execute() {
    unsafe {
        g_order = 0;
        defer g_order = g_order * 10 + 1;
        defer g_order = g_order * 10 + 2;
        defer g_order = g_order * 10 + 3;
    }
}

pub fn main() -> i32 {
    execute();
    unsafe {
        if g_order == 321 {
            return 0;
        } else {
            return 1;
        }
    }
}
"""
        code = self._compile_and_run(source)
        self.assertEqual(code, 0)

    def test_defer_on_early_return_with_value(self):
        source = """module test::defer_ret;

static mut g_cleanup: u32 = 0;

pub fn calculate(n: i32) -> i32 {
    unsafe {
        defer g_cleanup = 42;
    }
    if n > 0 {
        return n * 2;
    }
    return 0;
}

pub fn main() -> i32 {
    let res: i32 = calculate(5);
    unsafe {
        if res == 10 && g_cleanup == 42 {
            return 0;
        } else {
            return 1;
        }
    }
}
"""
        code = self._compile_and_run(source)
        self.assertEqual(code, 0)

    def test_raii_automatic_deinit_destruction(self):
        source = """module test::raii_guard;

static mut g_destructed: u32 = 0;

pub struct ResourceTracker {
    id: u32;

    pub fn deinit(&mut self) {
        unsafe {
            g_destructed = self.id;
        }
    }
}

pub fn execute_scope() -> i32 {
    let mut tracker: ResourceTracker = 0;
    tracker.id = 99;
    // When execute_scope exits, tracker goes out of scope and calls deinit!
    return 1;
}

pub fn main() -> i32 {
    let _r: i32 = execute_scope();
    unsafe {
        if g_destructed == 99 {
            return 0;
        } else {
            return 1;
        }
    }
}
"""
        code = self._compile_and_run(source)
        self.assertEqual(code, 0)

    def test_for_in_range_loop_execution(self):
        source = """module test::for_range;

pub fn main() -> i32 {
    let mut sum: u32 = 0;
    for i in 1..11 {
        sum = sum + (i as u32);
    }
    // sum of 1..10 = 55
    if sum == 55 {
        return 0;
    } else {
        return 1;
    }
}
"""
        code = self._compile_and_run(source)
        self.assertEqual(code, 0)

    def test_try_operator_on_result(self):
        source = """module test::try_op;

pub enum ResultCode {
    Ok = 0,
    Err = 1
}

pub struct ResultU32 {
    status: ResultCode;
    value: u32;

    pub fn ok(v: u32) -> ResultU32 {
        let mut r: ResultU32 = 0;
        r.status = ResultCode::Ok;
        r.value = v;
        return r;
    }

    pub fn err() -> ResultU32 {
        let mut r: ResultU32 = 0;
        r.status = ResultCode::Err;
        r.value = 0;
        return r;
    }
}

pub fn may_fail(success: bool) -> ResultU32 {
    if success {
        return ResultU32::ok(42);
    }
    return ResultU32::err();
}

pub fn compute_pipeline(flag: bool) -> ResultU32 {
    let val: u32 = may_fail(flag)?;
    return ResultU32::ok(val + 8);
}

pub fn main() -> i32 {
    let r1: ResultU32 = compute_pipeline(true);
    let r2: ResultU32 = compute_pipeline(false);
    if r1.status == ResultCode::Ok && r1.value == 50 && r2.status == ResultCode::Err {
        return 0;
    } else {
        return 1;
    }
}
"""
        code = self._compile_and_run(source)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
