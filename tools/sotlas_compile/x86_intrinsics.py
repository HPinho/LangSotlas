"""Extensão de backend x86-64 para o frontend Sotlas Bootstrap.

Mantém instruções privilegiadas, MMIO e entry stubs fora do compilador de alto nível.
O módulo registra assinaturas Sotlas e injeta somente wrappers C/assembly
freestanding mínimos, que o GCC reduz para instruções reais da CPU.
"""

from __future__ import annotations

_MARKER = "/* SOTLAS_X86_64_PRIVILEGED_INTRINSICS */"

_C_INTRINSICS = r'''

/* SOTLAS_X86_64_PRIVILEGED_INTRINSICS */
typedef struct __attribute__((packed)) {
    uint16_t limit;
    uint64_t base;
} __sotlas_x86_dt_ptr;

static inline void __lgdt(uint64_t address) {
    __asm__ __volatile__("lgdt (%0)" : : "r"((uintptr_t)address) : "memory");
}

static inline void __lidt(uint64_t address) {
    __asm__ __volatile__("lidt (%0)" : : "r"((uintptr_t)address) : "memory");
}

static inline void __gdt_activate_segments(uint64_t base,
                                           uint16_t limit,
                                           uint16_t code_selector,
                                           uint16_t data_selector) {
    __sotlas_x86_dt_ptr gdtr = { limit, base };
    __asm__ __volatile__(
        "lgdt %0\n\t"
        "movw %w2, %%ax\n\t"
        "movw %%ax, %%ds\n\t"
        "movw %%ax, %%es\n\t"
        "movw %%ax, %%ss\n\t"
        "leaq 1f(%%rip), %%rax\n\t"
        "pushq %1\n\t"
        "pushq %%rax\n\t"
        "lretq\n\t"
        "1:\n\t"
        :
        : "m"(gdtr), "r"((uint64_t)code_selector), "r"(data_selector)
        : "rax", "memory"
    );
}

static inline void __lidt_table(uint64_t base, uint16_t limit) {
    __sotlas_x86_dt_ptr idtr = { limit, base };
    __asm__ __volatile__("lidt %0" : : "m"(idtr) : "memory");
}

static inline void __ltr(uint16_t selector) {
    __asm__ __volatile__("ltr %w0" : : "r"(selector) : "memory");
}

static inline uint64_t __read_cr2(void) {
    uint64_t value;
    __asm__ __volatile__("mov %%cr2, %0" : "=r"(value) : : "memory");
    return value;
}

static inline uint64_t __read_cr3(void) {
    uint64_t value;
    __asm__ __volatile__("mov %%cr3, %0" : "=r"(value) : : "memory");
    return value;
}

static inline void __write_cr3(uint64_t value) {
    __asm__ __volatile__("mov %0, %%cr3" : : "r"(value) : "memory");
}

static inline void __invlpg(uint64_t address) {
    __asm__ __volatile__("invlpg (%0)" : : "r"((uintptr_t)address) : "memory");
}

static inline uint64_t __current_rsp(void) {
    uint64_t value;
    __asm__ __volatile__("mov %%rsp, %0" : "=r"(value));
    return value;
}

static inline bool __fpu_supported(void) {
    uint32_t a = 1, b, c, d;
    __asm__ __volatile__("cpuid" : "+a"(a), "=b"(b), "=c"(c), "=d"(d));
    return (d & (1u << 24)) != 0 && (d & (1u << 25)) != 0;
}

static inline void __fpu_enable(void) {
    uint64_t cr0, cr4;
    __asm__ __volatile__("mov %%cr0,%0; mov %%cr4,%1" : "=r"(cr0), "=r"(cr4));
    cr0 &= ~(1ull << 2);
    cr0 |= (1ull << 1);
    cr4 |= (1ull << 9) | (1ull << 10);
    __asm__ __volatile__("mov %0,%%cr0; mov %1,%%cr4; fninit"
                         : : "r"(cr0), "r"(cr4) : "memory");
}

static inline void __fpu_reset(void) {
    __asm__ __volatile__("fninit" : : : "memory");
}

static inline void __fxsave(uint64_t address) {
    __asm__ __volatile__("fxsave64 (%0)" : : "r"((uintptr_t)address) : "memory");
}

static inline void __fxrstor(uint64_t address) {
    __asm__ __volatile__("fxrstor64 (%0)" : : "r"((uintptr_t)address) : "memory");
}

static inline bool __fpu_round_trip_test(void) {
    struct __attribute__((aligned(16))) { unsigned char bytes[512]; } before, changed, observed;
    __asm__ __volatile__("fxsave64 %0" : "=m"(before) : : "memory");
    for (unsigned i = 0; i < 512; ++i) changed.bytes[i] = before.bytes[i];
    uint32_t *mxcsr = (uint32_t *)(void *)(changed.bytes + 24);
    *mxcsr = (*mxcsr & ~(3u << 13)) | (1u << 13);
    __asm__ __volatile__("fxrstor64 %0" : : "m"(changed) : "memory");
    __asm__ __volatile__("fxsave64 %0" : "=m"(observed) : : "memory");
    __asm__ __volatile__("fxrstor64 %0" : : "m"(before) : "memory");
    return (*(uint32_t *)(void *)(observed.bytes + 24) & (3u << 13)) == (1u << 13);
}

static inline void __dma_fence(void) {
    __asm__ __volatile__("mfence" : : : "memory");
}

static inline void __sfence(void) {
    __asm__ __volatile__("sfence" : : : "memory");
}

static inline void __lfence(void) {
    __asm__ __volatile__("lfence" : : : "memory");
}

/* xchg with a memory operand is implicitly locked on x86 and acts as the
 * full ordering primitive used by Sotlas spinlocks. */
static inline uint32_t __atomic_exchange_u32(uint64_t address, uint32_t value) {
    __asm__ __volatile__("xchgl %0,(%1)"
                         : "+r"(value)
                         : "r"((uintptr_t)address)
                         : "memory");
    return value;
}

static inline uint64_t __atomic_exchange_u64(uint64_t address, uint64_t value) {
    __asm__ __volatile__("xchgq %0,(%1)"
                         : "+r"(value)
                         : "r"((uintptr_t)address)
                         : "memory");
    return value;
}

/* lock xadd atomically adds value to *address and returns the OLD value. */
static inline uint64_t __atomic_add_u64(uint64_t address, uint64_t value) {
    __asm__ __volatile__("lock xaddq %0,(%1)"
                         : "+r"(value)
                         : "r"((uintptr_t)address)
                         : "memory");
    return value;
}

static inline uint32_t __atomic_add_u32(uint64_t address, uint32_t value) {
    __asm__ __volatile__("lock xaddl %0,(%1)"
                         : "+r"(value)
                         : "r"((uintptr_t)address)
                         : "memory");
    return value;
}

/* Subtract is add-of-negative; returns the OLD value. */
static inline uint64_t __atomic_sub_u64(uint64_t address, uint64_t value) {
    uint64_t neg = (uint64_t)(-(int64_t)value);
    __asm__ __volatile__("lock xaddq %0,(%1)"
                         : "+r"(neg)
                         : "r"((uintptr_t)address)
                         : "memory");
    return neg;
}

static inline uint32_t __atomic_sub_u32(uint64_t address, uint32_t value) {
    uint32_t neg = (uint32_t)(-(int32_t)value);
    __asm__ __volatile__("lock xaddl %0,(%1)"
                         : "+r"(neg)
                         : "r"((uintptr_t)address)
                         : "memory");
    return neg;
}

/* Relaxed atomic load — on x86 TSO, a plain mov is already acquire-like;
 * the compiler barrier prevents reordering at the IR level. */
static inline uint32_t __atomic_load_u32(uint64_t address) {
    uint32_t value = *(volatile uint32_t *)(uintptr_t)address;
    __asm__ __volatile__("" : : : "memory");
    return value;
}

static inline uint64_t __atomic_load_u64(uint64_t address) {
    uint64_t value = *(volatile uint64_t *)(uintptr_t)address;
    __asm__ __volatile__("" : : : "memory");
    return value;
}

/* Relaxed atomic store — compiler barrier + plain mov. */
static inline void __atomic_store_u32(uint64_t address, uint32_t value) {
    __asm__ __volatile__("" : : : "memory");
    *(volatile uint32_t *)(uintptr_t)address = value;
    __asm__ __volatile__("" : : : "memory");
}

static inline void __atomic_store_u64(uint64_t address, uint64_t value) {
    __asm__ __volatile__("" : : : "memory");
    *(volatile uint64_t *)(uintptr_t)address = value;
    __asm__ __volatile__("" : : : "memory");
}

/* lock cmpxchg — compare-and-swap. Returns the OLD value at address.
 * If old == expected, the swap happened; otherwise it did not. */
static inline uint64_t __atomic_cmpxchg_u64(uint64_t address, uint64_t expected, uint64_t desired) {
    uint64_t old = expected;
    __asm__ __volatile__("lock cmpxchgq %2,(%3)"
                         : "+a"(old)
                         : "a"(expected), "r"(desired), "r"((uintptr_t)address)
                         : "memory", "cc");
    return old;
}

static inline uint32_t __atomic_cmpxchg_u32(uint64_t address, uint32_t expected, uint32_t desired) {
    uint32_t old = expected;
    __asm__ __volatile__("lock cmpxchgl %2,(%3)"
                         : "+a"(old)
                         : "a"(expected), "r"(desired), "r"((uintptr_t)address)
                         : "memory", "cc");
    return old;
}

/* PAT slot 7 is programmed on every logical CPU before that CPU is released
 * to the scheduler. Bootstrap mappings keep using slot 0 (WB) or 3 (UC). */
static inline bool __pat_install_wc(void) {
    uint32_t a = 1, b, c, d;
    __asm__ __volatile__("cpuid" : "+a"(a), "=b"(b), "=c"(c), "=d"(d));
    if (!(d & (1u << 16))) return false;
    uint64_t flags, cr0, cr3;
    __asm__ __volatile__("pushfq; popq %0; cli; mov %%cr0,%1; mov %%cr3,%2"
                         : "=r"(flags), "=r"(cr0), "=r"(cr3) : : "memory");
    uint64_t uncached = (cr0 | (1ull << 30)) & ~(1ull << 29);
    __asm__ __volatile__("mov %0,%%cr0; wbinvd" : : "r"(uncached) : "memory");
    uint32_t lo, hi;
    __asm__ __volatile__("rdmsr" : "=a"(lo), "=d"(hi) : "c"(0x277));
    hi = (hi & 0x00ffffffu) | 0x01000000u;
    __asm__ __volatile__("wrmsr; wbinvd" : : "a"(lo), "d"(hi), "c"(0x277) : "memory");
    __asm__ __volatile__("mov %0,%%cr3; mov %1,%%cr0; pushq %2; popfq"
                         : : "r"(cr3), "r"(cr0), "r"(flags) : "memory", "cc");
    __asm__ __volatile__("rdmsr" : "=a"(lo), "=d"(hi) : "c"(0x277));
    return (hi >> 24) == 1;
}

static inline uint64_t __rdtsc(void) {
    uint32_t low, high;
    __asm__ __volatile__("rdtsc" : "=a"(low), "=d"(high));
    return ((uint64_t)high << 32) | low;
}

static inline void __cpu_pause(void) {
    __asm__ __volatile__("pause");
}

static inline void __scheduler_yield_interrupt(void) {
    __asm__ __volatile__("int $0x43" : : : "memory");
}

static inline bool __interrupts_enabled(void) {
    uint64_t flags;
    __asm__ __volatile__("pushfq; popq %0" : "=r"(flags) : : "memory");
    return (flags & (1ull << 9)) != 0;
}

static inline uint64_t __irq_save_disable(void) {
    uint64_t flags;
    __asm__ __volatile__("pushfq; popq %0; cli" : "=r"(flags) : : "memory");
    return flags;
}

/* Restore RFLAGS including IF via pushq/popfq. This is correct for nesting:
 * it restores exactly the interrupt state that was saved, without assuming
 * whether interrupts were enabled or disabled. The branch-based approach
 * (if IF then sti else cli) was correct but slower and lost other flags. */
static inline void __irq_restore(uint64_t flags) {
    __asm__ __volatile__("pushq %0; popfq" : : "r"(flags) : "memory", "cc");
}

static inline void __scheduler_block_switch(void) {
    __asm__ __volatile__("sti\n\tint $0x43" : : : "memory", "cc");
}

static inline uint32_t __mmio_read32(uint64_t address) {
    uint32_t value = *(volatile uint32_t *)(uintptr_t)address;
    __asm__ __volatile__("" : : : "memory");
    return value;
}

static inline void __mmio_write32(uint64_t address, uint32_t value) {
    __asm__ __volatile__("" : : : "memory");
    *(volatile uint32_t *)(uintptr_t)address = value;
    __asm__ __volatile__("" : : : "memory");
}

extern void sotlas_x86_post_cutover_entry(uint64_t argument);
__attribute__((naked, noreturn, unused)) static void
__stack_switch_to_post_cutover(uint64_t stack_top, uint64_t argument) {
    __asm__(
        "movq %rcx, %rsp\n\t"
        "andq $-16, %rsp\n\t"
        "movq %rdx, %rcx\n\t"
        "subq $32, %rsp\n\t"
        "call sotlas_x86_post_cutover_entry\n\t"
        "cli\n\t"
        "1: hlt\n\t"
        "jmp 1b\n\t"
    );
}

__attribute__((naked, noreturn, used)) static void
__enter_user(uint64_t entry, uint64_t user_stack) {
    __asm__(
        "cli\n\t"
        "pushq $0x23\n\t"
        "pushq %rdx\n\t"
        "pushq $0x202\n\t"
        "pushq $0x1b\n\t"
        "pushq %rcx\n\t"
        "iretq\n\t"
    );
}

__attribute__((weak)) void sotlas_x86_scheduler_thread_exit(void) {}
__attribute__((naked, noreturn, used)) static void __scheduler_thread_trampoline(void) {
    __asm__(
        "movq %r10, %rsp\n\t"
        "andq $-16, %rsp\n\t"
        "subq $32, %rsp\n\t"
        "sti\n\t"
        "call *%r11\n\t"
        "call sotlas_x86_scheduler_thread_exit\n\t"
        "cli\n\t"
        "1: hlt\n\t"
        "jmp 1b\n\t"
    );
}

static inline uint64_t __scheduler_thread_trampoline_address(void) {
    return (uint64_t)(uintptr_t)&__scheduler_thread_trampoline;
}
__attribute__((weak)) void sotlas_x86_scheduler_exit_probe_entry(void) {}
static inline uint64_t __scheduler_exit_probe_entry_address(void) { return (uint64_t)(uintptr_t)&sotlas_x86_scheduler_exit_probe_entry; }
__attribute__((weak)) void sotlas_x86_scheduler_idle_entry(void) {}
static inline uint64_t __scheduler_idle_entry_address(void) { return (uint64_t)(uintptr_t)&sotlas_x86_scheduler_idle_entry; }
__attribute__((weak)) void sotlas_x86_smp_ap_runtime_entry(void) {}
static inline uint64_t __smp_ap_runtime_entry_address(void) { return (uint64_t)(uintptr_t)&sotlas_x86_smp_ap_runtime_entry; }
__attribute__((weak)) void sotlas_x86_scheduler_smp_probe_entry(void) {}
static inline uint64_t __scheduler_smp_probe_entry_address(void) { return (uint64_t)(uintptr_t)&sotlas_x86_scheduler_smp_probe_entry; }
__attribute__((weak)) void sotlas_x86_scheduler_wait_probe_entry(void) {}
static inline uint64_t __scheduler_wait_probe_entry_address(void) { return (uint64_t)(uintptr_t)&sotlas_x86_scheduler_wait_probe_entry; }
__attribute__((weak)) void sotlas_x86_scheduler_wake_probe_entry(void) {}
static inline uint64_t __scheduler_wake_probe_entry_address(void) { return (uint64_t)(uintptr_t)&sotlas_x86_scheduler_wake_probe_entry; }
__attribute__((weak)) void sotlas_x86_userspace_bootstrap_entry(void) {}
static inline uint64_t __userspace_bootstrap_entry_address(void) { return (uint64_t)(uintptr_t)&sotlas_x86_userspace_bootstrap_entry; }

__attribute__((weak)) void sotlas_x86_exception_dispatch(uint64_t frame_address) { (void)frame_address; }
__attribute__((naked, used)) static void __sotlas_x86_exception_common(void) {
    __asm__(
        "movq %rsp, %rcx\n\t"
        "andq $-16, %rsp\n\t"
        "subq $32, %rsp\n\t"
        "call sotlas_x86_exception_dispatch\n\t"
        "cli\n\t"
        "1: hlt\n\t"
        "jmp 1b\n\t"
    );
}

#define SOTLAS_X86_ISR_NOERR(n) \
    __attribute__((naked, unused)) static void __sotlas_x86_isr_##n(void) { \
        __asm__("pushq $0\n\tpushq $" #n "\n\tjmp __sotlas_x86_exception_common"); \
    }
#define SOTLAS_X86_ISR_ERR(n) \
    __attribute__((naked, unused)) static void __sotlas_x86_isr_##n(void) { \
        __asm__("pushq $" #n "\n\tjmp __sotlas_x86_exception_common"); \
    }
SOTLAS_X86_ISR_NOERR(0)
SOTLAS_X86_ISR_NOERR(1)
SOTLAS_X86_ISR_NOERR(2)
SOTLAS_X86_ISR_NOERR(3)
SOTLAS_X86_ISR_NOERR(4)
SOTLAS_X86_ISR_NOERR(5)
SOTLAS_X86_ISR_NOERR(6)
SOTLAS_X86_ISR_NOERR(7)
SOTLAS_X86_ISR_ERR(8)
SOTLAS_X86_ISR_NOERR(9)
SOTLAS_X86_ISR_ERR(10)
SOTLAS_X86_ISR_ERR(11)
SOTLAS_X86_ISR_ERR(12)
SOTLAS_X86_ISR_ERR(13)
SOTLAS_X86_ISR_ERR(14)
SOTLAS_X86_ISR_NOERR(15)
SOTLAS_X86_ISR_NOERR(16)
SOTLAS_X86_ISR_ERR(17)
SOTLAS_X86_ISR_NOERR(18)
SOTLAS_X86_ISR_NOERR(19)
SOTLAS_X86_ISR_NOERR(20)
SOTLAS_X86_ISR_ERR(21)
SOTLAS_X86_ISR_NOERR(22)
SOTLAS_X86_ISR_NOERR(23)
SOTLAS_X86_ISR_NOERR(24)
SOTLAS_X86_ISR_NOERR(25)
SOTLAS_X86_ISR_NOERR(26)
SOTLAS_X86_ISR_NOERR(27)
SOTLAS_X86_ISR_NOERR(28)
SOTLAS_X86_ISR_ERR(29)
SOTLAS_X86_ISR_ERR(30)
SOTLAS_X86_ISR_NOERR(31)
#undef SOTLAS_X86_ISR_NOERR
#undef SOTLAS_X86_ISR_ERR

static inline uint64_t __exception_stub_address(uint16_t vector) {
    switch (vector) {
        case 0: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_0;
        case 1: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_1;
        case 2: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_2;
        case 3: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_3;
        case 4: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_4;
        case 5: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_5;
        case 6: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_6;
        case 7: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_7;
        case 8: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_8;
        case 9: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_9;
        case 10: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_10;
        case 11: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_11;
        case 12: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_12;
        case 13: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_13;
        case 14: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_14;
        case 15: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_15;
        case 16: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_16;
        case 17: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_17;
        case 18: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_18;
        case 19: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_19;
        case 20: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_20;
        case 21: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_21;
        case 22: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_22;
        case 23: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_23;
        case 24: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_24;
        case 25: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_25;
        case 26: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_26;
        case 27: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_27;
        case 28: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_28;
        case 29: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_29;
        case 30: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_30;
        case 31: return (uint64_t)(uintptr_t)&__sotlas_x86_isr_31;
        default: return 0;
    }
}

__attribute__((weak)) uint64_t sotlas_x86_irq_dispatch(uint64_t vector, uint64_t frame_address) { (void)vector; (void)frame_address; return 0; }
__attribute__((naked, used)) static void __sotlas_x86_irq_common(void) {
    __asm__(
        "pushq %rax\n\t"
        "pushq %rcx\n\t"
        "pushq %rdx\n\t"
        "pushq %rbx\n\t"
        "pushq %rbp\n\t"
        "pushq %rsi\n\t"
        "pushq %rdi\n\t"
        "pushq %r8\n\t"
        "pushq %r9\n\t"
        "pushq %r10\n\t"
        "pushq %r11\n\t"
        "pushq %r12\n\t"
        "pushq %r13\n\t"
        "pushq %r14\n\t"
        "pushq %r15\n\t"
        "movq %rsp, %r12\n\t"
        "movq 120(%r12), %rcx\n\t"
        "movq %r12, %rdx\n\t"
        "andq $-16, %rsp\n\t"
        "subq $32, %rsp\n\t"
        "call sotlas_x86_irq_dispatch\n\t"
        "testq %rax, %rax\n\t"
        "jnz 1f\n\t"
        "movq %r12, %rax\n\t"
        "1:\n\t"
        "movq %rax, %rsp\n\t"
        "popq %r15\n\t"
        "popq %r14\n\t"
        "popq %r13\n\t"
        "popq %r12\n\t"
        "popq %r11\n\t"
        "popq %r10\n\t"
        "popq %r9\n\t"
        "popq %r8\n\t"
        "popq %rdi\n\t"
        "popq %rsi\n\t"
        "popq %rbp\n\t"
        "popq %rbx\n\t"
        "popq %rdx\n\t"
        "popq %rcx\n\t"
        "popq %rax\n\t"
        "addq $8, %rsp\n\t"
        "iretq\n\t"
    );
}

/* Generate IRQ stubs for all usable vectors 32-255.  Vectors 0-31 are CPU
 * exceptions (handled above).  Each stub pushes its vector number and jumps
 * to the common dispatcher.  The macro-generated functions are emitted with
 * __attribute__((naked)) so they contain only the raw trampoline. */
#define SOTLAS_X86_IRQ_STUB(n) \
    __attribute__((naked, unused)) static void __sotlas_x86_irq_##n(void) { \
        __asm__("pushq $" #n "\n\tjmp __sotlas_x86_irq_common"); \
    }

/* PIC/IOAPIC remapped vectors and scheduler/IPI vectors */
SOTLAS_X86_IRQ_STUB(32)  SOTLAS_X86_IRQ_STUB(33)  SOTLAS_X86_IRQ_STUB(34)
SOTLAS_X86_IRQ_STUB(35)  SOTLAS_X86_IRQ_STUB(36)  SOTLAS_X86_IRQ_STUB(37)
SOTLAS_X86_IRQ_STUB(38)  SOTLAS_X86_IRQ_STUB(39)  SOTLAS_X86_IRQ_STUB(40)
SOTLAS_X86_IRQ_STUB(41)  SOTLAS_X86_IRQ_STUB(42)  SOTLAS_X86_IRQ_STUB(43)
SOTLAS_X86_IRQ_STUB(44)  SOTLAS_X86_IRQ_STUB(45)  SOTLAS_X86_IRQ_STUB(46)
SOTLAS_X86_IRQ_STUB(47)  SOTLAS_X86_IRQ_STUB(48)  SOTLAS_X86_IRQ_STUB(49)
SOTLAS_X86_IRQ_STUB(50)  SOTLAS_X86_IRQ_STUB(51)  SOTLAS_X86_IRQ_STUB(52)
SOTLAS_X86_IRQ_STUB(53)  SOTLAS_X86_IRQ_STUB(54)  SOTLAS_X86_IRQ_STUB(55)
SOTLAS_X86_IRQ_STUB(56)  SOTLAS_X86_IRQ_STUB(57)  SOTLAS_X86_IRQ_STUB(58)
SOTLAS_X86_IRQ_STUB(59)  SOTLAS_X86_IRQ_STUB(60)  SOTLAS_X86_IRQ_STUB(61)
SOTLAS_X86_IRQ_STUB(62)  SOTLAS_X86_IRQ_STUB(63)
/* Kernel scheduler, IPI, and device vectors */
SOTLAS_X86_IRQ_STUB(64)  SOTLAS_X86_IRQ_STUB(65)  SOTLAS_X86_IRQ_STUB(66)
SOTLAS_X86_IRQ_STUB(67)  SOTLAS_X86_IRQ_STUB(68)  SOTLAS_X86_IRQ_STUB(69)
SOTLAS_X86_IRQ_STUB(70)  SOTLAS_X86_IRQ_STUB(71)  SOTLAS_X86_IRQ_STUB(72)
SOTLAS_X86_IRQ_STUB(73)  SOTLAS_X86_IRQ_STUB(74)  SOTLAS_X86_IRQ_STUB(75)
SOTLAS_X86_IRQ_STUB(76)  SOTLAS_X86_IRQ_STUB(77)  SOTLAS_X86_IRQ_STUB(78)
SOTLAS_X86_IRQ_STUB(79)  SOTLAS_X86_IRQ_STUB(80)  SOTLAS_X86_IRQ_STUB(81)
SOTLAS_X86_IRQ_STUB(82)  SOTLAS_X86_IRQ_STUB(83)  SOTLAS_X86_IRQ_STUB(84)
SOTLAS_X86_IRQ_STUB(85)  SOTLAS_X86_IRQ_STUB(86)  SOTLAS_X86_IRQ_STUB(87)
SOTLAS_X86_IRQ_STUB(88)  SOTLAS_X86_IRQ_STUB(89)  SOTLAS_X86_IRQ_STUB(90)
SOTLAS_X86_IRQ_STUB(91)  SOTLAS_X86_IRQ_STUB(92)  SOTLAS_X86_IRQ_STUB(93)
SOTLAS_X86_IRQ_STUB(94)  SOTLAS_X86_IRQ_STUB(95)  SOTLAS_X86_IRQ_STUB(96)
SOTLAS_X86_IRQ_STUB(97)  SOTLAS_X86_IRQ_STUB(98)  SOTLAS_X86_IRQ_STUB(99)
SOTLAS_X86_IRQ_STUB(100) SOTLAS_X86_IRQ_STUB(101) SOTLAS_X86_IRQ_STUB(102)
SOTLAS_X86_IRQ_STUB(103) SOTLAS_X86_IRQ_STUB(104) SOTLAS_X86_IRQ_STUB(105)
SOTLAS_X86_IRQ_STUB(106) SOTLAS_X86_IRQ_STUB(107) SOTLAS_X86_IRQ_STUB(108)
SOTLAS_X86_IRQ_STUB(109) SOTLAS_X86_IRQ_STUB(110) SOTLAS_X86_IRQ_STUB(111)
SOTLAS_X86_IRQ_STUB(112) SOTLAS_X86_IRQ_STUB(113) SOTLAS_X86_IRQ_STUB(114)
SOTLAS_X86_IRQ_STUB(115) SOTLAS_X86_IRQ_STUB(116) SOTLAS_X86_IRQ_STUB(117)
SOTLAS_X86_IRQ_STUB(118) SOTLAS_X86_IRQ_STUB(119) SOTLAS_X86_IRQ_STUB(120)
SOTLAS_X86_IRQ_STUB(121) SOTLAS_X86_IRQ_STUB(122) SOTLAS_X86_IRQ_STUB(123)
SOTLAS_X86_IRQ_STUB(124) SOTLAS_X86_IRQ_STUB(125) SOTLAS_X86_IRQ_STUB(126)
SOTLAS_X86_IRQ_STUB(127) SOTLAS_X86_IRQ_STUB(128) SOTLAS_X86_IRQ_STUB(129)
SOTLAS_X86_IRQ_STUB(130) SOTLAS_X86_IRQ_STUB(131) SOTLAS_X86_IRQ_STUB(132)
SOTLAS_X86_IRQ_STUB(133) SOTLAS_X86_IRQ_STUB(134) SOTLAS_X86_IRQ_STUB(135)
SOTLAS_X86_IRQ_STUB(136) SOTLAS_X86_IRQ_STUB(137) SOTLAS_X86_IRQ_STUB(138)
SOTLAS_X86_IRQ_STUB(139) SOTLAS_X86_IRQ_STUB(140) SOTLAS_X86_IRQ_STUB(141)
SOTLAS_X86_IRQ_STUB(142) SOTLAS_X86_IRQ_STUB(143) SOTLAS_X86_IRQ_STUB(144)
SOTLAS_X86_IRQ_STUB(145) SOTLAS_X86_IRQ_STUB(146) SOTLAS_X86_IRQ_STUB(147)
SOTLAS_X86_IRQ_STUB(148) SOTLAS_X86_IRQ_STUB(149) SOTLAS_X86_IRQ_STUB(150)
SOTLAS_X86_IRQ_STUB(151) SOTLAS_X86_IRQ_STUB(152) SOTLAS_X86_IRQ_STUB(153)
SOTLAS_X86_IRQ_STUB(154) SOTLAS_X86_IRQ_STUB(155) SOTLAS_X86_IRQ_STUB(156)
SOTLAS_X86_IRQ_STUB(157) SOTLAS_X86_IRQ_STUB(158) SOTLAS_X86_IRQ_STUB(159)
SOTLAS_X86_IRQ_STUB(160) SOTLAS_X86_IRQ_STUB(161) SOTLAS_X86_IRQ_STUB(162)
SOTLAS_X86_IRQ_STUB(163) SOTLAS_X86_IRQ_STUB(164) SOTLAS_X86_IRQ_STUB(165)
SOTLAS_X86_IRQ_STUB(166) SOTLAS_X86_IRQ_STUB(167) SOTLAS_X86_IRQ_STUB(168)
SOTLAS_X86_IRQ_STUB(169) SOTLAS_X86_IRQ_STUB(170) SOTLAS_X86_IRQ_STUB(171)
SOTLAS_X86_IRQ_STUB(172) SOTLAS_X86_IRQ_STUB(173) SOTLAS_X86_IRQ_STUB(174)
SOTLAS_X86_IRQ_STUB(175) SOTLAS_X86_IRQ_STUB(176) SOTLAS_X86_IRQ_STUB(177)
SOTLAS_X86_IRQ_STUB(178) SOTLAS_X86_IRQ_STUB(179) SOTLAS_X86_IRQ_STUB(180)
SOTLAS_X86_IRQ_STUB(181) SOTLAS_X86_IRQ_STUB(182) SOTLAS_X86_IRQ_STUB(183)
SOTLAS_X86_IRQ_STUB(184) SOTLAS_X86_IRQ_STUB(185) SOTLAS_X86_IRQ_STUB(186)
SOTLAS_X86_IRQ_STUB(187) SOTLAS_X86_IRQ_STUB(188) SOTLAS_X86_IRQ_STUB(189)
SOTLAS_X86_IRQ_STUB(190) SOTLAS_X86_IRQ_STUB(191) SOTLAS_X86_IRQ_STUB(192)
SOTLAS_X86_IRQ_STUB(193) SOTLAS_X86_IRQ_STUB(194) SOTLAS_X86_IRQ_STUB(195)
SOTLAS_X86_IRQ_STUB(196) SOTLAS_X86_IRQ_STUB(197) SOTLAS_X86_IRQ_STUB(198)
SOTLAS_X86_IRQ_STUB(199) SOTLAS_X86_IRQ_STUB(200) SOTLAS_X86_IRQ_STUB(201)
SOTLAS_X86_IRQ_STUB(202) SOTLAS_X86_IRQ_STUB(203) SOTLAS_X86_IRQ_STUB(204)
SOTLAS_X86_IRQ_STUB(205) SOTLAS_X86_IRQ_STUB(206) SOTLAS_X86_IRQ_STUB(207)
SOTLAS_X86_IRQ_STUB(208) SOTLAS_X86_IRQ_STUB(209) SOTLAS_X86_IRQ_STUB(210)
SOTLAS_X86_IRQ_STUB(211) SOTLAS_X86_IRQ_STUB(212) SOTLAS_X86_IRQ_STUB(213)
SOTLAS_X86_IRQ_STUB(214) SOTLAS_X86_IRQ_STUB(215) SOTLAS_X86_IRQ_STUB(216)
SOTLAS_X86_IRQ_STUB(217) SOTLAS_X86_IRQ_STUB(218) SOTLAS_X86_IRQ_STUB(219)
SOTLAS_X86_IRQ_STUB(220) SOTLAS_X86_IRQ_STUB(221) SOTLAS_X86_IRQ_STUB(222)
SOTLAS_X86_IRQ_STUB(223) SOTLAS_X86_IRQ_STUB(224) SOTLAS_X86_IRQ_STUB(225)
SOTLAS_X86_IRQ_STUB(226) SOTLAS_X86_IRQ_STUB(227) SOTLAS_X86_IRQ_STUB(228)
SOTLAS_X86_IRQ_STUB(229) SOTLAS_X86_IRQ_STUB(230) SOTLAS_X86_IRQ_STUB(231)
SOTLAS_X86_IRQ_STUB(232) SOTLAS_X86_IRQ_STUB(233) SOTLAS_X86_IRQ_STUB(234)
SOTLAS_X86_IRQ_STUB(235) SOTLAS_X86_IRQ_STUB(236) SOTLAS_X86_IRQ_STUB(237)
SOTLAS_X86_IRQ_STUB(238) SOTLAS_X86_IRQ_STUB(239) SOTLAS_X86_IRQ_STUB(240)
SOTLAS_X86_IRQ_STUB(241) SOTLAS_X86_IRQ_STUB(242) SOTLAS_X86_IRQ_STUB(243)
SOTLAS_X86_IRQ_STUB(244) SOTLAS_X86_IRQ_STUB(245) SOTLAS_X86_IRQ_STUB(246)
SOTLAS_X86_IRQ_STUB(247) SOTLAS_X86_IRQ_STUB(248) SOTLAS_X86_IRQ_STUB(249)
SOTLAS_X86_IRQ_STUB(250) SOTLAS_X86_IRQ_STUB(251) SOTLAS_X86_IRQ_STUB(252)
SOTLAS_X86_IRQ_STUB(253) SOTLAS_X86_IRQ_STUB(254) SOTLAS_X86_IRQ_STUB(255)
#undef SOTLAS_X86_IRQ_STUB

static inline uint64_t __irq_stub_address(uint16_t vector) {
    switch (vector) {
        case 32: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_32;
        case 33: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_33;
        case 34: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_34;
        case 35: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_35;
        case 36: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_36;
        case 37: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_37;
        case 38: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_38;
        case 39: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_39;
        case 40: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_40;
        case 41: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_41;
        case 42: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_42;
        case 43: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_43;
        case 44: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_44;
        case 45: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_45;
        case 46: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_46;
        case 47: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_47;
        case 48: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_48;
        case 49: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_49;
        case 50: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_50;
        case 51: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_51;
        case 52: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_52;
        case 53: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_53;
        case 54: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_54;
        case 55: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_55;
        case 56: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_56;
        case 57: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_57;
        case 58: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_58;
        case 59: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_59;
        case 60: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_60;
        case 61: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_61;
        case 62: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_62;
        case 63: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_63;
        case 64: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_64;
        case 65: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_65;
        case 66: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_66;
        case 67: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_67;
        case 68: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_68;
        case 69: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_69;
        case 70: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_70;
        case 71: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_71;
        case 72: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_72;
        case 73: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_73;
        case 74: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_74;
        case 75: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_75;
        case 76: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_76;
        case 77: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_77;
        case 78: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_78;
        case 79: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_79;
        case 80: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_80;
        case 81: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_81;
        case 82: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_82;
        case 83: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_83;
        case 84: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_84;
        case 85: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_85;
        case 86: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_86;
        case 87: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_87;
        case 88: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_88;
        case 89: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_89;
        case 90: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_90;
        case 91: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_91;
        case 92: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_92;
        case 93: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_93;
        case 94: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_94;
        case 95: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_95;
        case 96: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_96;
        case 97: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_97;
        case 98: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_98;
        case 99: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_99;
        case 100: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_100;
        case 101: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_101;
        case 102: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_102;
        case 103: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_103;
        case 104: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_104;
        case 105: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_105;
        case 106: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_106;
        case 107: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_107;
        case 108: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_108;
        case 109: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_109;
        case 110: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_110;
        case 111: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_111;
        case 112: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_112;
        case 113: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_113;
        case 114: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_114;
        case 115: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_115;
        case 116: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_116;
        case 117: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_117;
        case 118: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_118;
        case 119: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_119;
        case 120: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_120;
        case 121: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_121;
        case 122: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_122;
        case 123: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_123;
        case 124: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_124;
        case 125: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_125;
        case 126: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_126;
        case 127: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_127;
        case 128: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_128;
        case 129: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_129;
        case 130: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_130;
        case 131: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_131;
        case 132: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_132;
        case 133: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_133;
        case 134: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_134;
        case 135: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_135;
        case 136: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_136;
        case 137: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_137;
        case 138: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_138;
        case 139: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_139;
        case 140: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_140;
        case 141: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_141;
        case 142: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_142;
        case 143: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_143;
        case 144: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_144;
        case 145: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_145;
        case 146: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_146;
        case 147: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_147;
        case 148: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_148;
        case 149: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_149;
        case 150: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_150;
        case 151: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_151;
        case 152: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_152;
        case 153: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_153;
        case 154: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_154;
        case 155: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_155;
        case 156: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_156;
        case 157: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_157;
        case 158: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_158;
        case 159: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_159;
        case 160: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_160;
        case 161: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_161;
        case 162: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_162;
        case 163: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_163;
        case 164: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_164;
        case 165: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_165;
        case 166: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_166;
        case 167: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_167;
        case 168: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_168;
        case 169: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_169;
        case 170: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_170;
        case 171: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_171;
        case 172: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_172;
        case 173: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_173;
        case 174: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_174;
        case 175: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_175;
        case 176: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_176;
        case 177: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_177;
        case 178: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_178;
        case 179: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_179;
        case 180: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_180;
        case 181: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_181;
        case 182: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_182;
        case 183: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_183;
        case 184: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_184;
        case 185: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_185;
        case 186: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_186;
        case 187: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_187;
        case 188: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_188;
        case 189: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_189;
        case 190: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_190;
        case 191: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_191;
        case 192: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_192;
        case 193: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_193;
        case 194: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_194;
        case 195: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_195;
        case 196: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_196;
        case 197: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_197;
        case 198: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_198;
        case 199: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_199;
        case 200: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_200;
        case 201: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_201;
        case 202: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_202;
        case 203: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_203;
        case 204: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_204;
        case 205: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_205;
        case 206: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_206;
        case 207: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_207;
        case 208: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_208;
        case 209: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_209;
        case 210: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_210;
        case 211: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_211;
        case 212: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_212;
        case 213: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_213;
        case 214: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_214;
        case 215: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_215;
        case 216: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_216;
        case 217: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_217;
        case 218: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_218;
        case 219: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_219;
        case 220: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_220;
        case 221: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_221;
        case 222: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_222;
        case 223: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_223;
        case 224: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_224;
        case 225: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_225;
        case 226: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_226;
        case 227: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_227;
        case 228: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_228;
        case 229: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_229;
        case 230: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_230;
        case 231: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_231;
        case 232: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_232;
        case 233: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_233;
        case 234: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_234;
        case 235: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_235;
        case 236: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_236;
        case 237: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_237;
        case 238: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_238;
        case 239: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_239;
        case 240: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_240;
        case 241: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_241;
        case 242: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_242;
        case 243: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_243;
        case 244: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_244;
        case 245: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_245;
        case 246: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_246;
        case 247: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_247;
        case 248: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_248;
        case 249: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_249;
        case 250: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_250;
        case 251: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_251;
        case 252: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_252;
        case 253: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_253;
        case 254: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_254;
        case 255: return (uint64_t)(uintptr_t)&__sotlas_x86_irq_255;
        default: return 0;
    }
}

/* ---- Control Register and MSR access ---- */

static inline uint64_t __read_cr0(void) {
    uint64_t value;
    __asm__ __volatile__("mov %%cr0, %0" : "=r"(value) : : "memory");
    return value;
}

static inline void __write_cr0(uint64_t value) {
    __asm__ __volatile__("mov %0, %%cr0" : : "r"(value) : "memory");
}

static inline uint64_t __read_cr4(void) {
    uint64_t value;
    __asm__ __volatile__("mov %%cr4, %0" : "=r"(value) : : "memory");
    return value;
}

static inline void __write_cr4(uint64_t value) {
    __asm__ __volatile__("mov %0, %%cr4" : : "r"(value) : "memory");
}

#ifndef __rdmsr_defined
#define __rdmsr_defined
static inline uint64_t __rdmsr(uint32_t msr) {
    uint32_t lo, hi;
    __asm__ __volatile__("rdmsr" : "=a"(lo), "=d"(hi) : "c"(msr));
    return ((uint64_t)hi << 32) | lo;
}

static inline void __wrmsr(uint32_t msr, uint64_t value) {
    uint32_t lo = (uint32_t)value;
    uint32_t hi = (uint32_t)(value >> 32);
    __asm__ __volatile__("wrmsr" : : "a"(lo), "d"(hi), "c"(msr) : "memory");
}
#endif

static inline void __swapgs(void) {
    __asm__ __volatile__("swapgs" : : : "memory");
}

static inline uint64_t __read_gs_base(void) {
    return __rdmsr(0xC0000101u);
}
'''


def install(bootstrap) -> None:
    """Registra os intrínsecos no módulo ``bootstrap`` de forma idempotente."""
    Type = bootstrap.Type
    Function = bootstrap.Function

    builtins = {
        # ---- Descriptor Table / TSS ----
        "__lgdt": Function("__lgdt", [("address", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
        "__lidt": Function("__lidt", [("address", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
        "__gdt_activate_segments": Function("__gdt_activate_segments", [("base", Type("u64")), ("limit", Type("u16")), ("code_selector", Type("u16")), ("data_selector", Type("u16"))], Type("void"), [], public=True, attributes=["@system"]),
        "__lidt_table": Function("__lidt_table", [("base", Type("u64")), ("limit", Type("u16"))], Type("void"), [], public=True, attributes=["@system"]),
        "__ltr": Function("__ltr", [("selector", Type("u16"))], Type("void"), [], public=True, attributes=["@system"]),

        # ---- Control Registers ----
        "__read_cr0": Function("__read_cr0", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__write_cr0": Function("__write_cr0", [("value", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
        "__read_cr2": Function("__read_cr2", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__read_cr3": Function("__read_cr3", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__write_cr3": Function("__write_cr3", [("value", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
        "__read_cr4": Function("__read_cr4", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__write_cr4": Function("__write_cr4", [("value", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),

        # ---- MSR access ----
        "__rdmsr": Function("__rdmsr", [("msr", Type("u32"))], Type("u64"), [], public=True, attributes=["@system"]),
        "__wrmsr": Function("__wrmsr", [("msr", Type("u32")), ("value", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),

        # ---- GS base / per-CPU ----
        "__swapgs": Function("__swapgs", [], Type("void"), [], public=True, attributes=["@system"]),
        "__read_gs_base": Function("__read_gs_base", [], Type("u64"), [], public=True, attributes=["@system"]),

        # ---- Scheduler / Stack / Userspace ----
        "__stack_switch_to_post_cutover": Function("__stack_switch_to_post_cutover", [("stack_top", Type("u64")), ("argument", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
        "__scheduler_thread_trampoline_address": Function("__scheduler_thread_trampoline_address", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__scheduler_exit_probe_entry_address": Function("__scheduler_exit_probe_entry_address", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__scheduler_idle_entry_address": Function("__scheduler_idle_entry_address", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__smp_ap_runtime_entry_address": Function("__smp_ap_runtime_entry_address", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__scheduler_smp_probe_entry_address": Function("__scheduler_smp_probe_entry_address", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__scheduler_wait_probe_entry_address": Function("__scheduler_wait_probe_entry_address", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__scheduler_wake_probe_entry_address": Function("__scheduler_wake_probe_entry_address", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__userspace_bootstrap_entry_address": Function("__userspace_bootstrap_entry_address", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__scheduler_yield_interrupt": Function("__scheduler_yield_interrupt", [], Type("void"), [], public=True, attributes=["@system"]),
        "__scheduler_block_switch": Function("__scheduler_block_switch", [], Type("void"), [], public=True, attributes=["@system"]),

        # ---- Interrupt control ----
        "__interrupts_enabled": Function("__interrupts_enabled", [], Type("bool"), [], public=True, attributes=["@system"]),
        "__irq_save_disable": Function("__irq_save_disable", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__irq_restore": Function("__irq_restore", [("flags", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),

        # ---- TLB / Page Table ----
        "__invlpg": Function("__invlpg", [("address", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),

        # ---- Memory Fences ----
        "__dma_fence": Function("__dma_fence", [], Type("void"), [], public=True, attributes=["@system"]),
        "__sfence": Function("__sfence", [], Type("void"), [], public=True, attributes=["@system"]),
        "__lfence": Function("__lfence", [], Type("void"), [], public=True, attributes=["@system"]),

        # ---- Atomic Operations ----
        "__atomic_exchange_u32": Function("__atomic_exchange_u32", [("address", Type("u64")), ("value", Type("u32"))], Type("u32"), [], public=True, attributes=["@system"]),
        "__atomic_exchange_u64": Function("__atomic_exchange_u64", [("address", Type("u64")), ("value", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
        "__atomic_add_u32": Function("__atomic_add_u32", [("address", Type("u64")), ("value", Type("u32"))], Type("u32"), [], public=True, attributes=["@system"]),
        "__atomic_add_u64": Function("__atomic_add_u64", [("address", Type("u64")), ("value", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
        "__atomic_sub_u32": Function("__atomic_sub_u32", [("address", Type("u64")), ("value", Type("u32"))], Type("u32"), [], public=True, attributes=["@system"]),
        "__atomic_sub_u64": Function("__atomic_sub_u64", [("address", Type("u64")), ("value", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
        "__atomic_load_u32": Function("__atomic_load_u32", [("address", Type("u64"))], Type("u32"), [], public=True, attributes=["@system"]),
        "__atomic_load_u64": Function("__atomic_load_u64", [("address", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
        "__atomic_store_u32": Function("__atomic_store_u32", [("address", Type("u64")), ("value", Type("u32"))], Type("void"), [], public=True, attributes=["@system"]),
        "__atomic_store_u64": Function("__atomic_store_u64", [("address", Type("u64")), ("value", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
        "__atomic_cmpxchg_u32": Function("__atomic_cmpxchg_u32", [("address", Type("u64")), ("expected", Type("u32")), ("desired", Type("u32"))], Type("u32"), [], public=True, attributes=["@system"]),
        "__atomic_cmpxchg_u64": Function("__atomic_cmpxchg_u64", [("address", Type("u64")), ("expected", Type("u64")), ("desired", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),

        # ---- PAT / Cache ----
        "__pat_install_wc": Function("__pat_install_wc", [], Type("bool"), [], public=True, attributes=["@system"]),

        # ---- Timing / Pause ----
        "__rdtsc": Function("__rdtsc", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__cpu_pause": Function("__cpu_pause", [], Type("void"), [], public=True, attributes=["@system"]),

        # ---- MMIO ----
        "__mmio_read32": Function("__mmio_read32", [("address", Type("u64"))], Type("u32"), [], public=True, attributes=["@system"]),
        "__mmio_write32": Function("__mmio_write32", [("address", Type("u64")), ("value", Type("u32"))], Type("void"), [], public=True, attributes=["@system"]),

        # ---- Exception / IRQ stubs ----
        "__exception_stub_address": Function("__exception_stub_address", [("vector", Type("u16"))], Type("u64"), [], public=True, attributes=["@system"]),
        "__irq_stub_address": Function("__irq_stub_address", [("vector", Type("u16"))], Type("u64"), [], public=True, attributes=["@system"]),

        # ---- Stack / Registers ----
        "__current_rsp": Function("__current_rsp", [], Type("u64"), [], public=True, attributes=["@system"]),
        "__enter_user": Function("__enter_user", [("entry", Type("u64")), ("user_stack", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),

        # ---- FPU / SSE ----
        "__fpu_supported": Function("__fpu_supported", [], Type("bool"), [], public=True, attributes=["@system"]),
        "__fpu_enable": Function("__fpu_enable", [], Type("void"), [], public=True, attributes=["@system"]),
        "__fpu_reset": Function("__fpu_reset", [], Type("void"), [], public=True, attributes=["@system"]),
        "__fxsave": Function("__fxsave", [("address", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
        "__fxrstor": Function("__fxrstor", [("address", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
        "__fpu_round_trip_test": Function("__fpu_round_trip_test", [], Type("bool"), [], public=True, attributes=["@system"]),
    }
    bootstrap.BUILTIN_FUNCTIONS.update(builtins)

    if _MARKER not in bootstrap.PREAMBLE:
        bootstrap.PREAMBLE = bootstrap.PREAMBLE.rstrip() + _C_INTRINSICS + "\n"
