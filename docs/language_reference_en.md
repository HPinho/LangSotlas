# Sotlas Language Reference Manual (v1.0)

## 1. Overview & Design Architecture

**Sotlas** is a deterministic, high-performance systems programming language designed for baremetal operating systems (BakenOS), real-time game engines, hardware drivers, AI/tensor accelerators, and low-latency systems software.

### Core Architectural Tenets
1. **Zero Mandatory Runtime**: Zero garbage collection, zero hidden runtime thread pools, and direct ABI compatibility with C11, C++, and Objective-C.
2. **Explicit Memory Topology**: Distinguishes CPU caches, memory-mapped I/O (MMIO), DMA-coherent buffers, and virtual address spaces at the type system level.
3. **Hardware Invariants & Safety**: Compile-time ownership validation, compile-time array and slice bounds safety, and hardware-grade assertions via `probe`.
4. **Deterministic Resource Management**: Scope-based LIFO cleanup via `defer`, RAII guard structures, and zero-allocation concurrency.

---

## 2. Primitive Types & Memory Layout

Sotlas defines fixed-width scalar types with unambiguous bit sizes:

| Type | Signed | Bit Width | C11 Representation |
|---|---|---|---|
| `u8` | No | 8 | `uint8_t` |
| `u16` | No | 16 | `uint16_t` |
| `u32` | No | 32 | `uint32_t` |
| `u64` | No | 64 | `uint64_t` |
| `usize` | No | Architecture Pointer Width | `size_t` |
| `i8` | Yes | 8 | `int8_t` |
| `i16` | Yes | 16 | `int16_t` |
| `i32` | Yes | 32 | `int32_t` |
| `i64` | Yes | 64 | `int64_t` |
| `isize` | Yes | Architecture Pointer Width | `intptr_t` |
| `f32` | Yes | 32 (IEEE-754 Single) | `float` |
| `f64` | Yes | 64 (IEEE-754 Double) | `double` |
| `bool` | No | 8 (`true` / `false`) | `bool` |
| `void` | - | 0 | `void` |

---

## 3. Memory Topology Pointers

Sotlas forbids unannotated raw pointer arithmetic on physical hardware. Every pointer declares its memory topology:

- `*rawphys T`: Volatile pointer to raw physical MMIO registers. Compilers never reorder or eliminate accesses.
- `*virtmap T`: Virtual memory mapping subject to page table invalidations and translation lookaside buffers.
- `*dmazone T`: Cache-coherent DMA ring buffers; stores automatically trigger hardware fences.
- `*portwire T`: Isolated port-mapped I/O bus lines (e.g. x86 `in`/`out`).
- `*voidzero`: Guarded null-trap pointer that hardware guarantees cannot point to executable code.

```sotlas
// Accessing a UART physical controller MMIO register
let uart_base: *rawphys u32 = 0x10000000 as *rawphys u32;
unsafe {
    *uart_base = 0x41; // 'A'
}
```

---

## 4. Ownership & Lifetime Discipline

Sotlas provides static, zero-runtime ownership semantics:

- `sole`: Exclusive ownership. Moves ownership on assignment; the source variable is invalidated.
- `island`: Thread-confined allocation. Cannot cross execution core boundaries without explicit handover.
- `whisper`: Read-only borrowed reference with lifetime guarantees.
- `direct`: Stack-allocated, direct-value transmission.
- `co-owned`: Reference-counted shared resource (ARC).

---

## 5. Resource Safety & The `defer` Statement

The `defer` statement schedules an expression or block to execute automatically upon exiting the enclosing scope in Last-In, First-Out (LIFO) order. Defer blocks execute on all return paths, including early returns:

```sotlas
pub fn process_resource() -> i32 {
    let mut lock: Mutex = mutex_new();
    mutex_lock(&lock);
    defer mutex_unlock(&lock); // Guarantees unlock on return

    if check_hardware_error() {
        return -1; // defer executes before returning
    }

    return 0; // defer executes before returning
}
```

---

## 6. Generics (`forge<T>`)

Generics in Sotlas are monomorphized at compile time, generating specialized zero-overhead types:

```sotlas
pub struct Pair forge<A, B> {
    pub first: A;
    pub second: B;
}

pub fn make_pair(a: u32, b: i64) -> Pair forge<u32, i64> {
    let mut p: Pair forge<u32, i64> = 0;
    p.first = a as u64;
    p.second = b;
    return p;
}
```

---

## 7. Systems Atomics & Hardware Barriers

Sotlas defines direct hardware intrinsics for lock-free and multi-core systems programming:

- `pulse`: Hardware full memory barrier (`mfence`).
- `__cpu_pause()`: Hint to spin-wait loops (`pause` on x86-64, `yield` on ARM64).
- `__atomic_exchange_u32(addr, val)`: Atomic exchange with sequential consistency.
- `__atomic_cmpxchg_u32(addr, expected, desired)`: Compare-and-swap primitive.

---

## 8. Pattern Matching & Hardware Invariants

- `probe <condition>, <message>;`: Hardware assert that raises an architectural trap if the condition is false.
- `discern / case`: Exhaustive pattern matching over enums and bit representations.

```sotlas
discern result_status {
    case ResultCode::Ok => { proceed(); }
    case ResultCode::TimedOut => { retry(); }
    case _ => { panic(); }
}
```
