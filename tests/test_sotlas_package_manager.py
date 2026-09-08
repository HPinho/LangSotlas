"""Testes unitários para o gerenciador de pacotes Sotlas (Sotlas.toml)."""
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.package_manager import PackageManifest, init_package, build_package, add_dependency


class SotlasPackageManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="sotlas_test_pkg_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_manifest_from_toml(self):
        toml_content = """
[package]
name = "my_app"
version = "0.2.1"
edition = "2026"
license = "MIT"
target_type = "bin"
authors = ["Dev Team <dev@bakenos.org>"]

[dependencies]
sotlas-core = "^0.3.0"
baken-driver = "1.0"
"""
        manifest = PackageManifest.from_toml_text(toml_content)
        self.assertEqual(manifest.name, "my_app")
        self.assertEqual(manifest.version, "0.2.1")
        self.assertEqual(manifest.license, "MIT")
        self.assertEqual(manifest.target_type, "bin")
        self.assertEqual(manifest.dependencies["sotlas-core"], "^0.3.0")
        self.assertEqual(manifest.dependencies["baken-driver"], "1.0")

    def test_init_binary_package(self):
        pkg_dir = self.temp_dir / "sample_app"
        toml_path = init_package(pkg_dir, "sample_app", is_lib=False)

        self.assertTrue(toml_path.exists())
        self.assertTrue((pkg_dir / "src" / "main.sotlas").exists())
        self.assertTrue((pkg_dir / ".gitignore").exists())

        manifest = PackageManifest.from_toml_text(toml_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest.name, "sample_app")
        self.assertEqual(manifest.target_type, "bin")

    def test_init_library_package(self):
        pkg_dir = self.temp_dir / "sample_lib"
        toml_path = init_package(pkg_dir, "sample_lib", is_lib=True)

        self.assertTrue(toml_path.exists())
        self.assertTrue((pkg_dir / "src" / "lib.sotlas").exists())

        manifest = PackageManifest.from_toml_text(toml_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest.name, "sample_lib")
        self.assertEqual(manifest.target_type, "lib")

    def test_build_package_flow(self):
        pkg_dir = self.temp_dir / "buildable_app"
        init_package(pkg_dir, "buildable_app", is_lib=False)

        res = build_package(pkg_dir)
        self.assertEqual(res, 0)
        self.assertTrue((pkg_dir / "build" / "buildable_app.c").exists())

    def test_add_dependency(self):
        pkg_dir = self.temp_dir / "dep_app"
        init_package(pkg_dir, "dep_app")

        add_dependency(pkg_dir, "sotlas-foundation", "^0.1.0")
        manifest = PackageManifest.from_toml_text((pkg_dir / "Sotlas.toml").read_text(encoding="utf-8"))
        self.assertIn("sotlas-foundation", manifest.dependencies)
        self.assertEqual(manifest.dependencies["sotlas-foundation"], "^0.1.0")


if __name__ == "__main__":
    unittest.main()
