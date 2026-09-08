"""Testes unitários para a biblioteca padrão hospedada (sotlas-foundation)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas import compile_source
from sotlas_compile import bootstrap as production_frontend


class SotlasFoundationTests(unittest.TestCase):
    def setUp(self):
        self.foundation_dir = ROOT / "stdlib" / "foundation"

    def test_alloc_module_parses_and_compiles(self):
        alloc_path = self.foundation_dir / "alloc.sotlas"
        self.assertTrue(alloc_path.exists())
        text = alloc_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(alloc_path))
        self.assertIn("ArenaAllocator", c_code)
        self.assertIn("MemoryBlock", c_code)

    def test_vec_module_parses_and_compiles(self):
        vec_path = self.foundation_dir / "vec.sotlas"
        self.assertTrue(vec_path.exists())
        text = vec_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(vec_path))
        self.assertIn("VecU32", c_code)
        self.assertIn("push", c_code)
        self.assertIn("pop", c_code)

    def test_string_buf_module_parses_and_compiles(self):
        sb_path = self.foundation_dir / "string_buf.sotlas"
        self.assertTrue(sb_path.exists())
        text = sb_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(sb_path))
        self.assertIn("StringBuf", c_code)
        self.assertIn("append_str", c_code)

    def test_hashmap_module_parses_and_compiles(self):
        hm_path = self.foundation_dir / "hashmap.sotlas"
        self.assertTrue(hm_path.exists())
        text = hm_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(hm_path))
        self.assertIn("HashMapU64", c_code)
        self.assertIn("hash_key", c_code)
        self.assertIn("insert", c_code)

    def test_file_module_parses_and_compiles(self):
        f_path = self.foundation_dir / "file.sotlas"
        self.assertTrue(f_path.exists())
        text = f_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(f_path))
        self.assertIn("File", c_code)
        self.assertIn("FileMode", c_code)


if __name__ == "__main__":
    unittest.main()
