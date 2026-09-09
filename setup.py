#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="sotlas",
    version="0.2.0",
    author="Hiago Pinho",
    license="Apache-2.0 WITH LLVM-exception",
    package_dir={"": "compiler"},
    packages=find_packages(where="compiler"),
    entry_points={
        "console_scripts": [
            "sotlas=sotlas.cli:main",
            "sotlasc=sotlas.cli:main",
            "sotlas-lsp=sotlas_compile.lsp:main",
        ],
    },
)
