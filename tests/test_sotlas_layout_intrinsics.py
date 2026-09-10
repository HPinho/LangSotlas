import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema
from sotlas.codegen_c import CodegenC


class SotlasLayoutIntrinsicsTests(unittest.TestCase):

    def compile_src(self, src: str) -> str:
        tokens = Lexer(src, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>").check()
        return CodegenC(ast).emit()

    def test_span_of_primitive(self):
        src = """module test::layout;
        pub fn get_u64_span() -> usize {
            return span_of::<u64>();
        }"""
        c = self.compile_src(src)
        self.assertIn("sizeof(uint64_t)", c)

    def test_align_of_struct(self):
        src = """module test::layout;
        @aligned(16)
        struct Vector4 {
            pub x: f32;
            pub y: f32;
            pub z: f32;
            pub w: f32;
        }
        pub fn get_vec_align() -> usize {
            return align_of::<Vector4>();
        }"""
        c = self.compile_src(src)
        self.assertIn("_Alignof(Vector4)", c)

    def test_stride_of_struct(self):
        src = """module test::layout;
        struct PageEntry {
            pub raw: u64;
        }
        pub fn get_stride() -> usize {
            return stride_of::<PageEntry>();
        }"""
        c = self.compile_src(src)
        self.assertIn("sizeof(PageEntry)", c)

    def test_field_offset_macro(self):
        src = """module test::layout;
        struct TaskControlBlock {
            pub pid: u32;
            pub rsp: u64;
            pub cr3: u64;
        }
        pub fn get_rsp_offset() -> usize {
            return field_offset!(TaskControlBlock, rsp);
        }"""
        c = self.compile_src(src)
        self.assertIn("offsetof(TaskControlBlock, rsp)", c)


if __name__ == "__main__":
    unittest.main()
