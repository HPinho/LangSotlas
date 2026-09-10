# The Sotlas Book — Systems Programming Without Fear

*A Comprehensive Guide to Modern, Deterministic, Baremetal Software Engineering.*

---

## Preface: The Systems Programmer's Dilemma

If you have ever spent a weekend debugging a memory corruption bug in C, or stared blankly at a 50-line C++ template error message, or fought with a borrow checker when all you wanted was an intrusive doubly-linked list for an OS scheduler, you understand the problem.

For decades, systems programming has forced developers into an uncomfortable compromise:
- **C11**: Beautifully simple, fast, but a loaded gun pointed directly at your foot.
- **C++20**: Powerful, but burdened with 40 years of backward-compatibility baggage and complex template metaprogramming.
- **Rust**: Safe, but fighting the borrow checker in cyclic graph data structures, intrusive kernels, and DMA rings requires `unsafe` everywhere anyway.
- **Zig**: Pragmatic, but lacks formal compile-time ownership tracking and memory topology semantics.

**Sotlas** was born to solve this. It is a language built from the silicon up for:
1. Baremetal Operating System Kernels (like **BakenOS**).
2. Hard Real-Time Game Engines & Simulators.
3. High-Throughput Network & Storage Engines.
4. AI / Tensor Compute Acceleration.

---

## Chapter 1: Hello, Systems

Here is the canonical first program in Sotlas:

```sotlas
module app::main;

pub fn main() -> i32 {
    let message: *const u8 = "Hello, Baremetal World!\n" as *const u8;
    probe message != nil, "pointer cannot be null";
    return 0;
}
```

Compile and run it in a single command with the native compiler:
```bash
sotlas run main.sotlas
```

---

## Chapter 2: The Physical Truth About Memory Topologies

Most programming languages pretend all memory is the same. To a modern CPU, this is an illusion. Accessing L1 cache takes 1 nanosecond; accessing a physical PCIe BAR over a bus takes microseconds; writing to non-cache-coherent DMA memory requires explicit CPU store-fences.

In Sotlas, pointer types reflect reality:

```sotlas
// 1. Raw Physical MMIO Pointer (Never cached, never reordered)
let uart_tx: *rawphys u32 = 0x09000000 as *rawphys u32;

// 2. Cache-Coherent DMA Ring Buffer
let dma_ring: *dmazone u64 = 0x80000000 as *dmazone u64;

// 3. Virtual Address Space Pointer
let user_page: *virtmap u8 = 0x7FFFFFFF0000 as *virtmap u8;
```

When you write to a `*rawphys` pointer, the compiler emits volatile accesses that the optimizer is strictly forbidden from reordering or deleting.

---

## Chapter 3: Clean Cleanup with `defer`

Resource leaks are the bane of long-running services and operating system kernels. Sotlas provides `defer`, which guarantees execution upon exiting the enclosing scope in LIFO (Last-In, First-Out) order:

```sotlas
pub fn write_hardware_packet(data: *const u8, len: usize) -> bool {
    let mut lock: Mutex = mutex_new();
    mutex_lock(&lock);
    defer mutex_unlock(&lock); // Runs automatically on ANY exit path!

    if len == 0 {
        return false; // mutex_unlock runs here
    }

    if !transmit_over_wire(data, len) {
        return false; // mutex_unlock runs here too!
    }

    return true; // and here!
}
```

---

## Chapter 4: Concurrency Without Magic

Sotlas believes that hidden thread pools and invisible green threads are acceptable for web servers, but unacceptable for game engines and operating systems. 

All concurrency primitives in `system::thread` and `system::sync` are explicit, zero-allocation, and direct:

```sotlas
import system::thread::*;

static mut g_buffer: [u64; 16] = 0;

pub fn worker_pipeline() {
    let mut ch: ChannelU64 = channel_new(g_buffer as *mut u64, 16);
    
    // Producers send bounded items
    channel_send(&ch, 100);
    channel_send(&ch, 200);

    // Consumers receive with atomic ordering
    let mut received: u64 = 0;
    if channel_recv(&ch, &received as *mut u64) {
        // processed received value
    }
}
```

---

## Chapter 5: Generics (`forge<T>`)

Generics in Sotlas are powered by `forge`. They are monomorphized into specialized, zero-overhead machine types at compile-time:

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

Under the hood, `Pair forge<u32, i64>` becomes `Pair_uint32_t_int64_t` with no runtime boxing, no type tags, and zero indirection.

---

## Chapter 6: Hardware Assertions via `probe`

In embedded software and kernel development, a failed invariant should trigger a CPU trap or panic immediately, rather than silently propagating corrupted state.

```sotlas
probe buffer_length <= MAX_PACKET_SIZE, "Network buffer exceeded MTU";
```

If the condition is false, `probe` records the diagnostic and triggers an architectural trap, giving you an exact register dump and backtrace.

---

## Conclusion: Write Code that Lasts

Sotlas is designed to build software that runs for years without leaking memory, without suffering from garbage collection pauses, and without fighting the compiler for the privilege of accessing physical silicon.

Welcome to the future of deterministic systems programming.
