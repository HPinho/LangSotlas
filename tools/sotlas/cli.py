"""Sotlas CLI — driver canônico e unificado para a linguagem Sotlas.

Uso:
    sotlas compile arquivo.sotlas [-o saída] [--target x86_64-freestanding] [--emit-c]
    sotlas check   arquivo.sotlas
    sotlas run     arquivo.sotlas
    sotlas dump-ast arquivo.sotlas
    sotlas dump-sir arquivo.sotlas
    sotlas dump-llvm arquivo.sotlas [--debug]
    sotlas fmt     arquivo.sotlas [--check]
    sotlas lint    arquivo.sotlas
    sotlas doc     arquivo.sotlas [-o saída.md]
    sotlas new     meu_projeto [--lib]
    sotlas init    [--lib]
    sotlas build   [--path .]
    sotlas add     dependencia [--version "^0.1.0"]
    sotlas lsp     [--stdio]
    sotlas test    [--pattern PATTERN]
    sotlas version
"""
from __future__ import annotations
import argparse
import sys
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from sotlas import compile_source, SOTLAS_VERSION, SotlasBootstrapError
from sotlas_compile import bootstrap as production_frontend
from sotlas.sir import SIRGenerator

SOTLAS_EXT = ".sotlas"


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sotlas",
        description=f"Compilador e Driver Sotlas v{SOTLAS_VERSION}",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Subcomando: compile
    cp = sub.add_parser("compile", help=f"Compila um arquivo {SOTLAS_EXT} para binário ou C11")
    cp.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")
    cp.add_argument("-o", "--output", default=None, help="Arquivo de saída")
    cp.add_argument(
        "--target",
        choices=["x86_64-freestanding", "host"],
        default="host",
        help="Alvo de compilação",
    )
    cp.add_argument(
        "--emit-c",
        action="store_true",
        help="Emite apenas o C11 intermediário (não invoca o compilador C)",
    )
    cp.add_argument(
        "--cc",
        default="gcc",
        help="Compilador C a invocar (padrão: gcc)",
    )

    # Subcomando: check
    chk = sub.add_parser("check", help="Executa lexer, parser, tipos e safety sem gerar código")
    chk.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    # Subcomando: run
    rn = sub.add_parser("run", help="Compila e executa um programa Sotlas diretamente")
    rn.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")
    rn.add_argument("--cc", default="gcc", help="Compilador C a invocar (padrão: gcc)")

    # Subcomando: dump-ast
    dast = sub.add_parser("dump-ast", help="Exibe a estrutura da AST analisada")
    dast.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    # Subcomando: dump-sir
    dsir = sub.add_parser("dump-sir", help="Exibe as instruções em formato SIR SSA")
    dsir.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")

    # Subcomando: dump-llvm
    dllvm = sub.add_parser("dump-llvm", help="Emite código intermediário LLVM IR (.ll) a partir do SIR")
    dllvm.add_argument("source", help=f"Arquivo fonte {SOTLAS_EXT}")
    dllvm.add_argument("--debug", action="store_true", help="Emite metadados de depuração DWARF")

    # Subcomando: fmt
    fmt_p = sub.add_parser("fmt", help="Formata arquivos de código-fonte Sotlas")
    fmt_p.add_argument("target", help="Arquivo ou diretório a formatar")
    fmt_p.add_argument("--check", action="store_true", help="Apenas verifica a formatação sem alterar arquivos")

    # Subcomando: lint
    lint_p = sub.add_parser("lint", help="Executa o linter de boas práticas e segurança")
    lint_p.add_argument("target", help="Arquivo ou diretório a analisar")

    # Subcomando: doc
    doc_p = sub.add_parser("doc", help="Gera documentação Markdown a partir de comentários '///'")
    doc_p.add_argument("target", help="Arquivo fonte .sotlas")
    doc_p.add_argument("-o", "--output", default=None, help="Arquivo de saída Markdown")

    # Subcomando: new
    new_p = sub.add_parser("new", help="Cria um novo projeto Sotlas com Sotlas.toml")
    new_p.add_argument("name", help="Nome do projeto")
    new_p.add_argument("--lib", action="store_true", help="Cria uma biblioteca em vez de binário executável")

    # Subcomando: init
    init_p = sub.add_parser("init", help="Inicializa um pacote Sotlas no diretório atual")
    init_p.add_argument("--lib", action="store_true", help="Inicializa como biblioteca")

    # Subcomando: build
    build_p = sub.add_parser("build", help="Compila um pacote Sotlas lendo o Sotlas.toml")
    build_p.add_argument("--path", default=".", help="Diretório do projeto (padrão: .)")

    # Subcomando: add
    add_p = sub.add_parser("add", help="Adiciona uma dependência ao Sotlas.toml")
    add_p.add_argument("dependency", help="Nome da dependência")
    add_p.add_argument("--version", default="^0.1.0", help="Especificação de versão (padrão: ^0.1.0)")

    # Subcomando: lsp
    lsp_p = sub.add_parser("lsp", help="Inicia o servidor de linguagem (Language Server Protocol)")
    lsp_p.add_argument("--stdio", action="store_true", default=True, help="Modo stdio padrão")

    # Subcomando: test
    tst = sub.add_parser("test", help="Executa a suíte de testes unitários da linguagem")
    tst.add_argument("-p", "--pattern", default="test_*.py", help="Padrão de arquivos de teste")

    # Subcomando: version
    sub.add_parser("version", help="Exibe a versão do compilador")

    args = parser.parse_args()

    if args.cmd == "version":
        print(f"Sotlas {SOTLAS_VERSION}")
        return 0
    if args.cmd == "check":
        return _run_check(args.source)
    if args.cmd == "compile":
        return _run_compile(args)
    if args.cmd == "run":
        return _run_exec(args)
    if args.cmd == "dump-ast":
        return _run_dump_ast(args.source)
    if args.cmd == "dump-sir":
        return _run_dump_sir(args.source)
    if args.cmd == "dump-llvm":
        return _run_dump_llvm(args.source, emit_debug=args.debug)
    if args.cmd == "fmt":
        return _run_fmt(args)
    if args.cmd == "lint":
        return _run_lint(args.target)
    if args.cmd == "doc":
        return _run_doc(args)
    if args.cmd == "new":
        return _run_new(args)
    if args.cmd == "init":
        return _run_init(args)
    if args.cmd == "build":
        return _run_build(args)
    if args.cmd == "add":
        return _run_add(args)
    if args.cmd == "lsp":
        return _run_lsp()
    if args.cmd == "test":
        return _run_tests(args.pattern)
    return 1


def _read_source(source_path: str) -> tuple[Path, str] | None:
    src = Path(source_path)
    if not src.exists():
        print(f"sotlas: erro: arquivo não encontrado: {source_path}", file=sys.stderr)
        return None
    if src.suffix not in (SOTLAS_EXT, ".st"):
        print(
            f"sotlas: aviso: extensão não reconhecida '{src.suffix}' (esperado {SOTLAS_EXT})",
            file=sys.stderr,
        )
    return src, src.read_text(encoding="utf-8")


def _run_check(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        module = production_frontend.parse(text, filename=source_path)
        production_frontend.check(module)
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1
    print(f"sotlas: ok — {source_path}")
    return 0


def _run_dump_ast(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        module = production_frontend.parse(text, filename=source_path)
        print(f"Module: {module.name}")
        for fn in module.functions:
            sys_tag = "@system " if getattr(fn, "is_system", False) else ""
            print(f"  {sys_tag}fn {fn.name}({len(fn.params)} params) -> {fn.result}")
        for s in module.structs:
            print(f"  struct {s.name} ({len(s.fields)} fields)")
        for e in module.enums:
            print(f"  enum {e.name} ({len(e.variants)} variants)")
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1
    return 0


def _run_dump_sir(source_path: str) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        module = production_frontend.parse(text, filename=source_path)
        gen = SIRGenerator()
        sir_mod = gen.generate_from_ast(module)
        print(sir_mod.dump())
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1
    return 0


def _run_dump_llvm(source_path: str, emit_debug: bool = False) -> int:
    loaded = _read_source(source_path)
    if loaded is None:
        return 1
    _, text = loaded
    try:
        from sotlas.codegen_llvm import CodegenLLVM
        module = production_frontend.parse(text, filename=source_path)
        gen = SIRGenerator()
        sir_mod = gen.generate_from_ast(module)
        llvm_ir = CodegenLLVM(sir_mod, emit_debug=emit_debug).emit()
        print(llvm_ir)
    except Exception as error:
        print(f"sotlas: erro ao emitir LLVM IR: {error}", file=sys.stderr)
        return 1
    return 0


def _run_fmt(args) -> int:
    target = Path(args.target)
    from sotlas.formatter import format_file
    if target.is_file():
        ok = format_file(target, check_only=args.check)
        return 0 if ok else 1
    elif target.is_dir():
        all_ok = True
        for p in target.glob("**/*.sotlas"):
            if not format_file(p, check_only=args.check):
                all_ok = False
        return 0 if all_ok else 1
    else:
        print(f"sotlas fmt: caminho não encontrado: {target}", file=sys.stderr)
        return 1


def _run_lint(target_path: str) -> int:
    target = Path(target_path)
    from sotlas.linter import lint_file
    if target.is_file():
        return lint_file(target)
    elif target.is_dir():
        ret = 0
        for p in target.glob("**/*.sotlas"):
            if lint_file(p) != 0:
                ret = 1
        return ret
    else:
        print(f"sotlas lint: caminho não encontrado: {target}", file=sys.stderr)
        return 1


def _run_doc(args) -> int:
    target = Path(args.target)
    from sotlas.docgen import docgen_file
    out_file = Path(args.output) if args.output else None
    return docgen_file(target, out_file)


def _run_new(args) -> int:
    from sotlas.package_manager import init_package
    target_dir = Path(args.name)
    init_package(target_dir, args.name, is_lib=args.lib)
    print(f"sotlas: novo pacote '{args.name}' criado com sucesso em {target_dir}")
    return 0


def _run_init(args) -> int:
    from sotlas.package_manager import init_package
    target_dir = Path.cwd()
    name = target_dir.name
    init_package(target_dir, name, is_lib=args.lib)
    print(f"sotlas: pacote '{name}' inicializado com sucesso em {target_dir}")
    return 0


def _run_build(args) -> int:
    from sotlas.package_manager import build_package
    target_dir = Path(args.path)
    return build_package(target_dir)


def _run_add(args) -> int:
    from sotlas.package_manager import add_dependency
    target_dir = Path.cwd()
    return add_dependency(target_dir, args.dependency, dep_spec=args.version)


def _run_compile(args) -> int:
    loaded = _read_source(args.source)
    if loaded is None:
        return 1
    src, text = loaded

    try:
        c_code = compile_source(text, args.source)
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = src.with_suffix(".bin" if not args.emit_c else ".c")

    if args.emit_c:
        c_path = out_path.with_suffix(".c")
        c_path.write_text(c_code, encoding="utf-8")
        print(f"sotlas: C11 emitido em {c_path}")
        return 0

    c_file = out_path.with_suffix(".c")
    c_file.write_text(c_code, encoding="utf-8")

    cc_flags = ["-std=c11", "-Wall", "-Wextra"]
    if args.target == "x86_64-freestanding":
        cc_flags += [
            "-ffreestanding", "-nostdlib", "-nostdinc",
            "-mno-red-zone", "-mno-mmx", "-mno-sse", "-mno-sse2",
        ]

    cmd = [args.cc, str(c_file), "-o", str(out_path)] + cc_flags
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"sotlas: erro do compilador C:\n{result.stderr}", file=sys.stderr)
            return result.returncode
        print(f"sotlas: binário gerado em {out_path}")
        return 0
    except FileNotFoundError:
        print(
            f"sotlas: compilador C '{args.cc}' não encontrado — use --emit-c para gerar apenas o C11",
            file=sys.stderr,
        )
        return 1


def _run_exec(args) -> int:
    loaded = _read_source(args.source)
    if loaded is None:
        return 1
    src, text = loaded

    try:
        c_code = compile_source(text, args.source)
    except SotlasBootstrapError as error:
        print(f"sotlas: erro: {error}", file=sys.stderr)
        return 1

    exe_path = src.with_suffix(".exe" if sys.platform == "win32" else ".out")
    c_file = src.with_suffix(".tmp.c")
    c_file.write_text(c_code, encoding="utf-8")

    cmd = [args.cc, "-std=c11", str(c_file), "-o", str(exe_path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"sotlas: erro de compilação C:\n{res.stderr}", file=sys.stderr)
            return res.returncode
        run_res = subprocess.run([str(exe_path)])
        return run_res.returncode
    finally:
        c_file.unlink(missing_ok=True)
        exe_path.unlink(missing_ok=True)


def _run_lsp() -> int:
    try:
        from sotlas_compile.lsp import run_stdio_server
        return run_stdio_server()
    except Exception as e:
        print(f"sotlas: erro ao iniciar LSP: {e}", file=sys.stderr)
        return 1


def _run_tests(pattern: str) -> int:
    import unittest
    tests_dir = _ROOT / "tests" if (_ROOT / "tests").is_dir() else _ROOT.parent / "tests"
    suite = unittest.defaultTestLoader.discover(str(tests_dir), pattern=pattern)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())