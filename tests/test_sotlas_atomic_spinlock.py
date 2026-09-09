"""Tests for atomic SpinLock and barrier specialization in system::sync."""
import sys
import os
import unittest
from pathlib import Path

# Ensure the compiler package is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas_compile import bootstrap, frontend_extensions, x86_intrinsics


def _backend():
    """Return a clean backend with extensions and x86 intrinsics loaded."""
    import importlib
    importlib.reload(bootstrap)
    frontend_extensions.install(bootstrap)
    x86_intrinsics.install(bootstrap)
    return bootstrap


class TestAtomicSpinLock(unittest.TestCase):
    """Verify that the stdlib SpinLock uses atomic xchg, not check-then-set."""

    def test_sync_module_has_correct_structure(self):
        """sync.sotlas must have the correct module declaration and struct."""
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        self.assertIn("module system::sync", src)
        self.assertIn("pub struct SpinLock", src)

    def test_bootstrap_parses_and_checks_sync_module(self):
        """bootstrap.py must parse and typecheck sync.sotlas cleanly with struct methods."""
        b = _backend()
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        mod = b.parse(src)
        self.assertGreaterEqual(len(mod.structs), 2)
        fn_names = [f.name for f in mod.functions]
        self.assertIn("SpinLock_lock", fn_names)
        self.assertIn("SpinLock_unlock", fn_names)
        self.assertIn("SpinLock_try_lock", fn_names)
        b.check(mod)

    def test_spinlock_lock_uses_atomic_exchange(self):
        """SpinLock.lock source must call __atomic_exchange_u32, not check-then-set."""
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        self.assertIn("__atomic_exchange_u32", src,
                       "SpinLock.lock must use __atomic_exchange_u32 (xchg), "
                       "not a non-atomic store")
        # Must NOT have the old pattern: `self.locked = 1` as lock acquisition
        # (the only `= 0` should be in new() and in unlock's xchg, and `= 1`
        # should only appear in xchg call args)
        lines = src.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped == "self.locked = 1;":
                self.fail("SpinLock must NOT use plain 'self.locked = 1' — "
                          "this is a non-atomic store that causes SMP race conditions")

    def test_spinlock_unlock_uses_fence(self):
        """SpinLock.unlock source must emit a fence before releasing."""
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        # Find the unlock function and verify it calls a fence
        unlock_idx = src.find("fn unlock")
        self.assertGreater(unlock_idx, 0, "SpinLock must have unlock method")
        unlock_body = src[unlock_idx:unlock_idx + 500]
        has_fence = ("__dma_fence" in unlock_body or "pulse()" in unlock_body)
        self.assertTrue(has_fence,
                        "SpinLock.unlock must emit a memory fence before releasing")

    def test_spinlock_lock_no_check_then_set(self):
        """SpinLock.lock must NOT use the old non-atomic pattern."""
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        # The old broken pattern was:
        #   while self.locked != 0 { cpu_pause(); }
        #   self.locked = 1;
        # This must not exist anymore.
        self.assertNotIn("while self.locked != 0", src,
                          "SpinLock must NOT use 'while self.locked != 0' — "
                          "this is a non-atomic check that causes SMP race conditions")

    def test_try_lock_exists(self):
        """sync.sotlas must export a try_lock method."""
        b = _backend()
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        self.assertIn("try_lock", src, "SpinLock must have a try_lock method")

    def test_pulse_store_exists(self):
        """sync.sotlas must export pulse_store (sfence)."""
        b = _backend()
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        self.assertIn("pulse_store", src, "sync module must have pulse_store (sfence)")

    def test_pulse_load_exists(self):
        """sync.sotlas must export pulse_load (lfence)."""
        b = _backend()
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        self.assertIn("pulse_load", src, "sync module must have pulse_load (lfence)")

    def test_compiler_fence_exists(self):
        """sync.sotlas must export compiler_fence."""
        src = (ROOT / "stdlib" / "system" / "sync.sotlas").read_text(encoding="utf-8")
        self.assertIn("compiler_fence", src, "sync module must have compiler_fence")


class TestBarrierIntrinsics(unittest.TestCase):
    """Verify that sfence/lfence intrinsics are registered in the backend."""

    def test_sfence_registered(self):
        b = _backend()
        self.assertIn("__sfence", b.BUILTIN_FUNCTIONS,
                       "__sfence must be registered as builtin")

    def test_lfence_registered(self):
        b = _backend()
        self.assertIn("__lfence", b.BUILTIN_FUNCTIONS,
                       "__lfence must be registered as builtin")

    def test_dma_fence_still_registered(self):
        b = _backend()
        self.assertIn("__dma_fence", b.BUILTIN_FUNCTIONS,
                       "__dma_fence (mfence) must remain registered")


class TestAtomicIntrinsics(unittest.TestCase):
    """Verify that the expanded atomic intrinsics are registered."""

    def test_atomic_exchange_u64(self):
        b = _backend()
        self.assertIn("__atomic_exchange_u64", b.BUILTIN_FUNCTIONS)

    def test_atomic_add_u64(self):
        b = _backend()
        self.assertIn("__atomic_add_u64", b.BUILTIN_FUNCTIONS)

    def test_atomic_sub_u64(self):
        b = _backend()
        self.assertIn("__atomic_sub_u64", b.BUILTIN_FUNCTIONS)

    def test_atomic_load_u32(self):
        b = _backend()
        self.assertIn("__atomic_load_u32", b.BUILTIN_FUNCTIONS)

    def test_atomic_store_u32(self):
        b = _backend()
        self.assertIn("__atomic_store_u32", b.BUILTIN_FUNCTIONS)

    def test_atomic_cmpxchg_u64(self):
        b = _backend()
        self.assertIn("__atomic_cmpxchg_u64", b.BUILTIN_FUNCTIONS)

    def test_cr0_registered(self):
        b = _backend()
        self.assertIn("__read_cr0", b.BUILTIN_FUNCTIONS)
        self.assertIn("__write_cr0", b.BUILTIN_FUNCTIONS)

    def test_cr4_registered(self):
        b = _backend()
        self.assertIn("__read_cr4", b.BUILTIN_FUNCTIONS)
        self.assertIn("__write_cr4", b.BUILTIN_FUNCTIONS)

    def test_rdmsr_wrmsr_registered(self):
        b = _backend()
        self.assertIn("__rdmsr", b.BUILTIN_FUNCTIONS)
        self.assertIn("__wrmsr", b.BUILTIN_FUNCTIONS)

    def test_swapgs_registered(self):
        b = _backend()
        self.assertIn("__swapgs", b.BUILTIN_FUNCTIONS)

    def test_read_gs_base_registered(self):
        b = _backend()
        self.assertIn("__read_gs_base", b.BUILTIN_FUNCTIONS)


if __name__ == "__main__":
    unittest.main()
