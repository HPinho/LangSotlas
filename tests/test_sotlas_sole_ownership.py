import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError
from sotlas.codegen_c import CodegenC


class SotlasSoleOwnershipTests(unittest.TestCase):

    def check_src(self, src: str):
        tokens = Lexer(src, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>").check()
        return ast

    def compile_src(self, src: str) -> str:
        ast = self.check_src(src)
        return CodegenC(ast).emit()

    def test_normal_struct_is_copyable(self):
        src = """module test::copyable;
        struct Point {
            pub x: i32;
            pub y: i32;
        }
        pub fn main() -> i32 {
            let p1 = Point { x: 10, y: 20 };
            let p2 = p1; // cópia normal permitida
            return p1.x + p2.y;
        }"""
        c = self.compile_src(src)
        self.assertIn("p1 = (Point){", c)
        self.assertIn("p2 = p1;", c)

    def test_sole_struct_moved_on_assignment(self):
        src = """module test::sole_move;
        sole struct FileDesc {
            pub fd: i32;
        }
        pub fn main() -> i32 {
            let f1 = FileDesc { fd: 3 };
            let f2 = f1; // posse transferida para f2
            return f1.fd; // ERRO: f1 foi transferido!
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        self.assertIn("uso inválido de recurso 'sole' 'f1' após transferência (handover)", str(ctx.exception))

    def test_sole_struct_valid_use_after_move_dest(self):
        src = """module test::sole_ok;
        sole struct FileDesc {
            pub fd: i32;
        }
        pub fn main() -> i32 {
            let f1 = FileDesc { fd: 3 };
            let f2 = f1; // transferido
            return f2.fd; // f2 é o novo dono soberano: VÁLIDO
        }"""
        c = self.compile_src(src)
        self.assertIn("f2 = f1;", c)
        self.assertIn("return f2.fd;", c)

    def test_sole_struct_consumed_by_value_call(self):
        src = """module test::sole_call;
        sole struct LockHandle {
            pub id: u32;
        }
        fn close_handle(h: LockHandle) {
        }
        pub fn main() {
            let lk = LockHandle { id: 1 };
            close_handle(lk); // consumido por valor
            let id2 = lk.id; // ERRO: lk foi consumido
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        self.assertIn("uso inválido de recurso 'sole' 'lk' após transferência (handover)", str(ctx.exception))

    def test_handover_statement_invalidates_source(self):
        src = """module test::handover_stmt;
        sole struct Channel {
            pub id: u64;
        }
        pub fn main() -> u64 {
            let ch = Channel { id: 99 };
            handover ch;
            return ch.id; // ERRO: ch foi transferido por handover
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        self.assertIn("uso inválido de recurso 'sole' 'ch' após transferência (handover)", str(ctx.exception))

    def test_handover_rejected_on_non_sole_type(self):
        src = """module test::handover_reject;
        pub fn main() {
            let num: i32 = 42;
            handover num; // ERRO: num não é sole
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        self.assertIn("'handover' só pode ser aplicado a variáveis 'sole'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
