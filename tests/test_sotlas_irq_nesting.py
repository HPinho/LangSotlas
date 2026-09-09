"""Tests for IRQ nesting safety and irq_restore correctness."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas_compile import bootstrap, frontend_extensions, x86_intrinsics


def _backend():
    import importlib
    importlib.reload(bootstrap)
    frontend_extensions.install(bootstrap)
    x86_intrinsics.install(bootstrap)
    return bootstrap


class TestIrqRestore(unittest.TestCase):
    """Verify that __irq_restore uses pushfq/popfq, not branch-based sti/cli."""

    def test_irq_restore_uses_popfq(self):
        """The C preamble must contain pushq/popfq for __irq_restore, not a branch."""
        b = _backend()
        preamble = b.PREAMBLE
        # Find the __irq_restore function in the preamble
        start = preamble.find("__irq_restore")
        self.assertGreater(start, 0, "__irq_restore must be in the preamble")
        # Get the function body (next ~10 lines)
        body = preamble[start:start + 500]
        self.assertIn("popfq", body,
                       "__irq_restore must use popfq for correct RFLAGS restoration.\n"
                       f"Found: {body[:200]}")

    def test_irq_restore_no_branch(self):
        """__irq_restore must NOT use if (flags & ...) branch pattern."""
        b = _backend()
        preamble = b.PREAMBLE
        start = preamble.find("static inline void __irq_restore")
        end = preamble.find("}", start + 1)
        body = preamble[start:end + 1] if end > start else ""
        # The old pattern was: if (flags & (1ull << 9)) { sti } else { cli }
        # The new pattern should be: pushq %0; popfq
        self.assertNotIn("1ull << 9", body,
                          "__irq_restore should not branch on IF bit; use pushq/popfq")

    def test_irq_save_disable_preserves_flags(self):
        """__irq_save_disable must save flags before disabling interrupts."""
        b = _backend()
        preamble = b.PREAMBLE
        start = preamble.find("static inline uint64_t __irq_save_disable")
        end = preamble.find("}", start + 1) if start >= 0 else -1
        body = preamble[start:end + 1] if end > start else ""
        self.assertIn("pushfq", body,
                       "__irq_save_disable must pushfq to save flags")
        self.assertIn("cli", body,
                       "__irq_save_disable must cli after saving flags")


class TestIrqIntrinsicsModule(unittest.TestCase):
    """Verify that system::intrinsics provides IRQ save/restore wrappers."""

    def test_intrinsics_has_irq_save_disable(self):
        src = (ROOT / "stdlib" / "system" / "intrinsics.sotlas").read_text(encoding="utf-8")
        self.assertIn("irq_save_disable", src,
                       "system::intrinsics must export irq_save_disable()")

    def test_intrinsics_has_irq_restore(self):
        src = (ROOT / "stdlib" / "system" / "intrinsics.sotlas").read_text(encoding="utf-8")
        self.assertIn("irq_restore", src,
                       "system::intrinsics must export irq_restore()")

    def test_intrinsics_has_interrupts_enabled(self):
        src = (ROOT / "stdlib" / "system" / "intrinsics.sotlas").read_text(encoding="utf-8")
        self.assertIn("interrupts_enabled", src,
                       "system::intrinsics must export interrupts_enabled()")

    def test_intrinsics_documents_nesting(self):
        """The documentation must explain that cli/sti breaks nesting."""
        src = (ROOT / "stdlib" / "system" / "intrinsics.sotlas").read_text(encoding="utf-8")
        self.assertIn("nesting", src.lower(),
                       "intrinsics.sotlas must document nesting safety")


class TestIrqStubsCoverage(unittest.TestCase):
    """Verify that IRQ stubs cover the full usable range, not just 5 vectors."""

    def test_irq_stubs_cover_64_to_255(self):
        """The C preamble must have stubs for at least vectors 32-255."""
        b = _backend()
        preamble = b.PREAMBLE
        for vec in (32, 48, 64, 96, 128, 192, 254, 255):
            marker = f"__sotlas_x86_irq_{vec}"
            self.assertIn(marker, preamble,
                           f"IRQ stub for vector {vec} must exist in preamble")

    def test_irq_stub_address_returns_nonzero(self):
        """The switch in __irq_stub_address must handle vectors beyond 64-68."""
        b = _backend()
        preamble = b.PREAMBLE
        # Verify the switch statement in __irq_stub_address covers more vectors
        self.assertIn("case 128:", preamble,
                       "__irq_stub_address switch must handle vector 128")
        self.assertIn("case 200:", preamble,
                       "__irq_stub_address switch must handle vector 200")


if __name__ == "__main__":
    unittest.main()
