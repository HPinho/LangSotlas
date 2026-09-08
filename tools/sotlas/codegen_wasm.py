"""Sotlas CodegenWASM — Emissor Nativo WebAssembly (Bypass de C11/C99).

Este módulo compila a AST/SIR de Sotlas diretamente para WebAssembly (WAT e WASM),
permitindo a execução em navegadores, runtimes de sistemas (Wasmtime, Wasmer)
e no Sotlas Studio sem requerer compiladores C (GCC/Clang/MSVC) instalados.
"""
from __future__ import annotations
from io import StringIO
from typing import Dict, List, Optional, Set
from .token_types import TK
from .ast_nodes import *


WASM_TYPE_MAP: Dict[str, str] = {
    "Void": "void",
    "void": "void",
    "Bool": "i32",
    "bool": "i32",
    "UInt8": "i32",
    "Int8": "i32",
    "u8": "i32",
    "i8": "i32",
    "UInt16": "i32",
    "Int16": "i32",
    "u16": "i32",
    "i16": "i32",
    "UInt32": "i32",
    "Int32": "i32",
    "u32": "i32",
    "i32": "i32",
    "UInt64": "i64",
    "Int64": "i64",
    "u64": "i64",
    "i64": "i64",
    "USize": "i32",
    "ISize": "i32",
    "usize": "i32",
    "isize": "i32",
    "Float32": "f32",
    "f32": "f32",
    "Float64": "f64",
    "f64": "f64",
    "string": "i32",
    "String": "i32",
}


def to_wasm_type(t: Optional[TypeNode]) -> Optional[str]:
    if not t:
        return None
    if t.is_topology_ptr or t.topology_ptr:
        return "i32"  # Wasm32 ponteiro linear de memória
    if t.primitive:
        from .token_types import PRIMITIVE_C_MAP
        name = PRIMITIVE_C_MAP.get(t.primitive, "int")
        if "64" in name:
            return "i64"
        if "float" in name:
            return "f32"
        if "double" in name:
            return "f64"
        return "i32"
    if t.name in WASM_TYPE_MAP:
        res = WASM_TYPE_MAP[t.name]
        return None if res == "void" else res
    return "i32"


class CodegenWasm:
    """Emissor de WebAssembly Text Format (WAT) a partir da AST Sotlas."""

    def __init__(self, ast: SourceFileNode) -> None:
        self._ast = ast
        self._out = StringIO()
        self._indent = 0
        self._string_table: Dict[str, int] = {}
        self._next_data_offset = 1024
        self._locals: Set[str] = set()

    def _w(self, s: str) -> None:
        self._out.write(s)

    def _line(self, s: str = "") -> None:
        self._out.write("  " * self._indent + s + "\n")

    def _indent_inc(self) -> None:
        self._indent += 1

    def _indent_dec(self) -> None:
        self._indent = max(0, self._indent - 1)

    def emit_wat(self) -> str:
        self._out = StringIO()
        self._indent = 0
        mod_name = ".".join(self._ast.module.path)

        self._line(f";; Módulo Sotlas WebAssembly: {mod_name}")
        self._line("(module")
        self._indent_inc()

        # Imports do runtime de console/host
        self._line('(import "env" "print_i32" (func $print_i32 (param i32)))')
        self._line('(import "env" "print_f64" (func $print_f64 (param f64)))')
        self._line('(import "env" "print_str" (func $print_str (param i32 i32)))')
        self._line('(import "env" "panic" (func $panic))')

        # Memória linear de 1 página (64KB) exportada para acesso do host
        self._line('(memory (export "memory") 1)')

        # Pré-coleta de literais de string
        self._collect_strings(self._ast)

        # Segmentos de dados para strings constantes
        for text, offset in self._string_table.items():
            escaped = text.replace('"', '\\"')
            self._line(f'(data (i32.const {offset}) "{escaped}\\00")')

        # Emissão de funções
        for decl in self._ast.decls:
            if isinstance(decl, FnDeclNode):
                self._emit_fn(decl)
            elif isinstance(decl, StructDeclNode):
                for m in decl.members:
                    if isinstance(m, FnDeclNode):
                        m2 = FnDeclNode(m.span, m.directives, m.is_pub, m.is_irqfree,
                                        m.is_async, m.is_moldable, m.is_reshape,
                                        f"{decl.name}__{m.name}", m.generics, m.params, m.ret, m.body)
                        self._emit_fn(m2)

        self._indent_dec()
        self._line(")")
        return self._out.getvalue()

    def _collect_strings(self, node: Any, visited: Optional[Set[int]] = None) -> None:
        if visited is None:
            visited = set()
        if node is None or id(node) in visited:
            return
        visited.add(id(node))

        if isinstance(node, LiteralNode) and node.kind == TK.STR_LIT:
            if node.value not in self._string_table:
                self._string_table[node.value] = self._next_data_offset
                self._next_data_offset += len(node.value.encode("utf-8")) + 4
            return

        if isinstance(node, list):
            for item in node:
                self._collect_strings(item, visited)
        elif hasattr(node, "__dataclass_fields__"):
            for f in node.__dataclass_fields__:
                if f != "span":
                    self._collect_strings(getattr(node, f), visited)

    def _emit_fn(self, decl: FnDeclNode) -> None:
        if decl.body is None:
            return

        ret_type = to_wasm_type(decl.ret)
        params_sig = []
        for p in decl.params:
            ptype = to_wasm_type(p.type_ann) or "i32"
            params_sig.append(f"(param ${p.name} {ptype})")

        res_sig = f"(result {ret_type})" if ret_type and ret_type != "void" else ""
        header = f"(func ${decl.name} (export \"{decl.name}\") {' '.join(params_sig)} {res_sig}".strip()
        self._line(header)
        self._indent_inc()

        self._locals = {p.name for p in decl.params}
        # Coletar variáveis locais
        for st in decl.body:
            if isinstance(st, LocalVarDeclNode) and st.name not in self._locals:
                wtype = to_wasm_type(st.type_ann) or "i32"
                self._line(f"(local ${st.name} {wtype})")
                self._locals.add(st.name)

        for st in decl.body:
            self._emit_stmt(st)

        self._indent_dec()
        self._line(")")

    def _emit_stmt(self, stmt: StmtNode) -> None:
        if isinstance(stmt, LocalVarDeclNode):
            if stmt.init:
                self._emit_expr(stmt.init)
                self._line(f"local.set ${stmt.name}")
        elif isinstance(stmt, AssignmentNode):
            if isinstance(stmt.target, IdentNode):
                self._emit_expr(stmt.value)
                self._line(f"local.set ${stmt.target.name}")
            elif isinstance(stmt.target, UnaryExprNode) and stmt.target.op == TK.STAR:
                # Store em memória linear
                self._emit_expr(stmt.target.operand)
                self._emit_expr(stmt.value)
                self._line("i32.store")
        elif isinstance(stmt, ReturnNode):
            if stmt.value:
                self._emit_expr(stmt.value)
            self._line("return")
        elif isinstance(stmt, IfNode):
            self._emit_expr(stmt.condition)
            self._line("(if")
            self._indent_inc()
            self._line("(then")
            self._indent_inc()
            for st in stmt.then_body:
                self._emit_stmt(st)
            self._indent_dec()
            self._line(")")
            if stmt.else_body:
                self._line("(else")
                self._indent_inc()
                if isinstance(stmt.else_body, IfNode):
                    self._emit_stmt(stmt.else_body)
                else:
                    for st in stmt.else_body:
                        self._emit_stmt(st)
                self._indent_dec()
                self._line(")")
            self._indent_dec()
            self._line(")")
        elif isinstance(stmt, WhileNode):
            self._line("(block $break_loop")
            self._indent_inc()
            self._line("(loop $continue_loop")
            self._indent_inc()
            self._emit_expr(stmt.condition)
            self._line("i32.eqz")
            self._line("br_if $break_loop")
            for st in stmt.body:
                self._emit_stmt(st)
            self._line("br $continue_loop")
            self._indent_dec()
            self._line(")")
            self._indent_dec()
            self._line(")")
        elif isinstance(stmt, DiscernStmtNode):
            self._emit_discern(stmt)
        elif isinstance(stmt, ProbeStmtNode):
            self._emit_expr(stmt.condition)
            self._line("i32.eqz")
            self._line("(if (then (call $panic)))")
        elif isinstance(stmt, PulseStmtNode):
            # No Wasm single-thread, pulse é uma cerca semântica segura
            self._line(";; pulse fence")
        elif isinstance(stmt, ExprStmtNode):
            self._emit_expr(stmt.expr)
            # Descartar valor residual se a expressão retornar algo
            if isinstance(stmt.expr, CallExprNode):
                self._line("drop")

    def _emit_discern(self, stmt: DiscernStmtNode) -> None:
        """Emite discern como uma cascata determinística de blocos Wasm."""
        self._line(";; discern")
        for i, case in enumerate(stmt.cases):
            self._emit_expr(stmt.subject)
            if case.pattern.kind == "literal":
                val = self._emit_expr_to_str(case.pattern.value)
                self._line(f"i32.const {val}")
                self._line("i32.eq")
            elif case.pattern.kind == "enum_variant":
                self._line(f";; variant {case.pattern.value}")
                self._line(f"i32.const {i}")
                self._line("i32.eq")
            else:
                self._line("i32.const 1")  # wildcard sempre casa

            self._line("(if")
            self._indent_inc()
            self._line("(then")
            self._indent_inc()
            for st in case.body:
                self._emit_stmt(st)
            self._indent_dec()
            self._line(")")
            self._indent_dec()
            self._line(")")

        if stmt.default_case:
            self._line(";; discern default")
            for st in stmt.default_case:
                self._emit_stmt(st)

    def _emit_expr_to_str(self, expr: ExprNode) -> str:
        if isinstance(expr, LiteralNode):
            return str(expr.value)
        return "0"

    def _emit_expr(self, expr: ExprNode) -> None:
        if isinstance(expr, LiteralNode):
            if expr.kind in (TK.INT_LIT, TK.KW_TRUE, TK.KW_FALSE):
                v = 1 if expr.kind == TK.KW_TRUE else (0 if expr.kind == TK.KW_FALSE else expr.value)
                self._line(f"i32.const {v}")
            elif expr.kind == TK.FLOAT_LIT:
                self._line(f"f64.const {expr.value}")
            elif expr.kind == TK.STR_LIT:
                offset = self._string_table.get(expr.value, 0)
                self._line(f"i32.const {offset}")
            elif expr.kind == TK.KW_NIL:
                self._line("i32.const 0")
        elif isinstance(expr, IdentNode):
            if expr.name in self._locals:
                self._line(f"local.get ${expr.name}")
            else:
                self._line(f"local.get ${expr.name}")
        elif isinstance(expr, BinaryExprNode):
            self._emit_expr(expr.left)
            self._emit_expr(expr.right)
            bin_ops = {
                TK.PLUS: "i32.add",
                TK.MINUS: "i32.sub",
                TK.STAR: "i32.mul",
                TK.SLASH: "i32.div_s",
                TK.PERCENT: "i32.rem_s",
                TK.EQ: "i32.eq",
                TK.NEQ: "i32.ne",
                TK.LT: "i32.lt_s",
                TK.LTE: "i32.le_s",
                TK.GT: "i32.gt_s",
                TK.GTE: "i32.ge_s",
                TK.LAND: "i32.and",
                TK.LOR: "i32.or",
                TK.XOR: "i32.xor",
                TK.SHL: "i32.shl",
                TK.SHR: "i32.shr_s",
            }
            op = bin_ops.get(expr.op, "i32.add")
            self._line(op)
        elif isinstance(expr, UnaryExprNode):
            self._emit_expr(expr.operand)
            if expr.op == TK.NOT:
                self._line("i32.eqz")
            elif expr.op == TK.MINUS:
                self._line("i32.const -1")
                self._line("i32.mul")
            elif expr.op == TK.STAR:
                self._line("i32.load")
        elif isinstance(expr, CallExprNode):
            for arg in expr.args:
                self._emit_expr(arg.value)
            callee_name = expr.callee.name if isinstance(expr.callee, IdentNode) else "unknown"
            self._line(f"call ${callee_name}")
        elif isinstance(expr, CastExprNode):
            self._emit_expr(expr.expr)
        else:
            self._line("i32.const 0")
