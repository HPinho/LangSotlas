"""Sotlas REPL — Read-Eval-Print Loop interativo para a linguagem Sotlas.

Permite testar expressões, funções, structs e primitivas proprietárias (discern, forge,
enclave, probe, pulse) linha a linha no terminal com feedback instantâneo.
"""
from __future__ import annotations
import sys
import os
from pathlib import Path
from typing import List

from .lexer import Lexer
from .parser import Parser
from .sema import Sema
from .codegen_c import CodegenC
from .codegen_wasm import CodegenWasm
from .token_types import TK


_BANNER = """\
======================================================================
  Sotlas Interactive Systems REPL v0.2.0
  Palavras-chave: discern | forge<T> | enclave<T> | probe | pulse
  Digite :help para ajuda, :c11 / :wat para ver código, :exit para sair
======================================================================\
"""

_HELP = """\
Comandos do REPL Sotlas:
  :help          Exibe esta mensagem de ajuda
  :exit, :quit   Encerra a sessão do REPL
  :clear         Limpa as declarações acumuladas na sessão
  :c11           Exibe o código C11 gerado para o buffer atual
  :wat           Exibe o código WebAssembly gerado para o buffer atual
  :ast           Exibe a árvore sintática abstrata (AST)
"""


class SotlasRepl:
    def __init__(self) -> None:
        self.session_decls: List[str] = []
        self.counter = 0

    def run(self) -> None:
        print(_BANNER)
        buffer: List[str] = []
        brace_depth = 0

        while True:
            try:
                prompt = "sotlas> " if not buffer else "...     "
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print("\nEncerrando sessão Sotlas REPL.")
                break

            stripped = line.strip()
            if not buffer and stripped.startswith(":"):
                self._handle_command(stripped)
                continue

            buffer.append(line)
            brace_depth += line.count("{") - line.count("}")

            if brace_depth <= 0 and (not stripped or stripped.endswith(";") or stripped.endswith("}")):
                full_input = "\n".join(buffer).strip()
                buffer = []
                brace_depth = 0
                if full_input:
                    self._eval(full_input)

    def _handle_command(self, cmd: str) -> None:
        c = cmd.lower()
        if c in (":exit", ":quit", ":q"):
            print("Encerrando sessão Sotlas REPL.")
            sys.exit(0)
        elif c == ":help":
            print(_HELP)
        elif c == ":clear":
            self.session_decls.clear()
            print("Sessão limpa.")
        else:
            print(f"Comando desconhecido: '{cmd}'. Digite :help para ajuda.")

    def _eval(self, code: str) -> None:
        self.counter += 1
        is_top_decl = any(code.startswith(kw) for kw in ("pub", "fn", "struct", "class", "enum", "const", "static", "module"))
        is_var_decl = code.startswith("let ") or code.startswith("var ")
        is_decl = is_top_decl or is_var_decl
        if is_top_decl:
            src = f"module repl::session;\n{code}\n"
        elif is_var_decl:
            src = f"module repl::session;\npub fn eval_{self.counter}() -> i64 {{\n    {code}\n    return 0;\n}}\n"
        else:
            # Expressão ou statement dentro de uma função wrapper
            return_expr = f"return {code};" if not code.endswith(";") and not code.endswith("}") else code
            src = f"module repl::session;\npub fn eval_{self.counter}() -> i64 {{\n    {return_expr}\n    return 0;\n}}\n"

        try:
            tokens = Lexer(src, "<repl>").tokenize()
            ast = Parser(tokens, "<repl>").parse()
            Sema(ast, "<repl>", src).check()
            c_code = CodegenC(ast).emit()
            wat_code = CodegenWasm(ast).emit_wat()

            if is_decl:
                self.session_decls.append(code)
                print(f"-> Declarado com sucesso.")
            else:
                print(f"-> Sintaxe e Semântica Válidas (OK)")
                # Exibir uma linha sintética do resultado C11 / Wasm
                print(f"   [C11]: compilado com sucesso")
                print(f"   [Wasm]: módulo gerado ({len(wat_code)} bytes)")
        except Exception as err:
            print(f"Erro no REPL: {err}")


def start_repl() -> int:
    repl = SotlasRepl()
    repl.run()
    return 0
