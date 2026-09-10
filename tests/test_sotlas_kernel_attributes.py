"""Testes para atributos de kernel (@naked, @interrupt, @aligned, @section) e declaração de registradores (register)."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas_compile import bootstrap
from sotlas.llvm_toolchain import default_toolchain


class TestSotlasKernelAttributes(unittest.TestCase):
    def test_kernel_attributes_emission(self):
        source = """module test::kernel_attrs;

@aligned(16)
pub struct PageTableEntry {
    entry: u64;
}

@section(".text.boot")
@naked
pub fn boot_entry() {
    unsafe {
        __cli();
    }
}

@interrupt
pub fn timer_irq_handler() {
    unsafe {
        __sti();
    }
}

@noinline
pub fn compute(x: u32) -> u32 {
    return x * 2;
}
"""
        c_code = bootstrap.compile_source(source)
        self.assertIn("__attribute__((aligned(16)))", c_code)
        self.assertIn("__attribute__((section(\".text.boot\")))", c_code)
        self.assertIn("__attribute__((naked))", c_code)
        self.assertIn("__attribute__((interrupt))", c_code)
        self.assertIn("__attribute__((noinline))", c_code)

    def test_register_bitfield_declaration_and_emission(self):
        source = """module test::registers;

pub register ControlReg: u32 {
    enable: u1 [0],
    mode: u3 [1..3],
    prescaler: u8 [8..15],
    reserved: u16 [16..31]
}

pub fn configure(ctrl: *mut ControlReg) {
    unsafe {
        (*ctrl).enable = 1;
        (*ctrl).mode = 3;
    }
}

pub fn get_raw(ctrl: ControlReg) -> u32 {
    return ctrl.raw;
}
"""
        c_code = bootstrap.compile_source(source)
        self.assertIn("typedef union ControlReg {", c_code)
        self.assertIn("uint32_t raw;", c_code)
        self.assertIn("struct __attribute__((packed)) {", c_code)
        self.assertIn("enable : 1;", c_code)
        self.assertIn("mode : 3;", c_code)
        self.assertIn("prescaler : 8;", c_code)
        self.assertIn("reserved : 16;", c_code)

    def test_register_end_to_end_native_execution(self):
        source = """module test::reg_exec;

pub register Reg32: u32 {
    flag_a: u1 [0],
    flag_b: u1 [1],
    val: u6 [2..7]
}

pub fn main() -> i32 {
    let mut reg: Reg32 = 0;
    reg.flag_a = 1;
    reg.flag_b = 1;
    reg.val = 5; // binary 000101, shifted by 2: 5 << 2 = 20. Total raw = 1 | 2 | 20 = 23
    if reg.raw == 23 && reg.flag_a == 1 && reg.val == 5 {
        return 0;
    } else {
        return 1;
    }
}
"""
        import tempfile, subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            c_file = tmp / "test_reg.c"
            exe_file = tmp / "test_reg.exe"
            c_code = bootstrap.compile_source(source)
            c_file.write_text(c_code, encoding="utf-8")

            obj_file = tmp / "test_reg.obj"
            default_toolchain.compile_c_to_obj(c_file, obj_file, opt_level=2)
            default_toolchain.link_native_binary([obj_file], exe_file)

            res = subprocess.run([str(exe_file)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
