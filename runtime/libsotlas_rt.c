/* libsotlas_rt.c — Standalone Freestanding Runtime para Sotlas. */
#include "libsotlas_rt.h"

/* Buffer estático de fallback para ambientes freestanding (1 MB de pool) */
#define DEFAULT_HEAP_POOL_SIZE (1024 * 1024)
static uint8_t s_freestanding_pool[DEFAULT_HEAP_POOL_SIZE];
static size_t  s_pool_offset = 0;

static SotlasAllocFn s_custom_alloc = NULL;
static SotlasFreeFn  s_custom_free  = NULL;
static SotlasPanicFn s_panic_handler = NULL;

void sotlas_rt_set_allocator(SotlasAllocFn alloc_fn, SotlasFreeFn free_fn) {
    s_custom_alloc = alloc_fn;
    s_custom_free  = free_fn;
}

void sotlas_rt_set_panic_handler(SotlasPanicFn handler) {
    s_panic_handler = handler;
}

void* sotlas_rt_alloc_aligned(size_t size, size_t alignment) {
    if (s_custom_alloc) {
        return s_custom_alloc(size, alignment);
    }
    if (alignment == 0) alignment = 8;

    /* Alinhamento no pool freestanding */
    size_t current = (size_t)(s_freestanding_pool + s_pool_offset);
    size_t remainder = current % alignment;
    size_t padding = (remainder == 0) ? 0 : (alignment - remainder);

    if (s_pool_offset + padding + size > DEFAULT_HEAP_POOL_SIZE) {
        sotlas_rt_panic("Out of memory in freestanding heap pool", __FILE__, __LINE__);
        return NULL;
    }

    s_pool_offset += padding;
    void *ptr = (void*)(s_freestanding_pool + s_pool_offset);
    s_pool_offset += size;
    return ptr;
}

void* sotlas_rt_alloc(size_t size) {
    return sotlas_rt_alloc_aligned(size, 8);
}

void* sotlas_rt_realloc(void *ptr, size_t new_size) {
    if (!ptr) {
        return sotlas_rt_alloc(new_size);
    }
    void *new_ptr = sotlas_rt_alloc(new_size);
    if (!new_ptr) return NULL;

    /* Cópia simples (tamanho conservador) */
    uint8_t *dst = (uint8_t*)new_ptr;
    uint8_t *src = (uint8_t*)ptr;
    for (size_t i = 0; i < new_size; ++i) {
        dst[i] = src[i];
    }
    return new_ptr;
}

void sotlas_rt_free(void *ptr) {
    if (s_custom_free && ptr) {
        s_custom_free(ptr);
    }
    /* No bump allocator simples freestanding, free é no-op */
}

void sotlas_rt_arc_retain(void *object) {
    if (!object) return;
    SotlasArcHeader *header = ((SotlasArcHeader*)object) - 1;
    __atomic_add_fetch(&header->strong_count, 1, __ATOMIC_SEQ_CST);
}

void sotlas_rt_arc_release(void *object, void (*destructor)(void *)) {
    if (!object) return;
    SotlasArcHeader *header = ((SotlasArcHeader*)object) - 1;
    int64_t count = __atomic_sub_fetch(&header->strong_count, 1, __ATOMIC_SEQ_CST);
    if (count <= 0) {
        if (destructor) {
            destructor(object);
        }
        sotlas_rt_free(header);
    }
}

void sotlas_rt_panic(const char *message, const char *file, uint32_t line) {
    if (s_panic_handler) {
        s_panic_handler(message, file, line);
        return;
    }
    /* Fallback freestanding: loop infinito de parada */
    (void)message; (void)file; (void)line;
    while (1) {
#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__)
        __asm__ volatile("hlt");
#elif defined(__aarch64__)
        __asm__ volatile("wfi");
#endif
    }
}

bool sotlas_rt_slice_eq(const uint8_t *a, size_t a_len, const uint8_t *b, size_t b_len) {
    if (a_len != b_len) return false;
    if (a == b) return true;
    for (size_t i = 0; i < a_len; ++i) {
        if (a[i] != b[i]) return false;
    }
    return true;
}

size_t sotlas_rt_slice_copy(uint8_t *dst, size_t dst_len, const uint8_t *src, size_t src_len) {
    size_t copy_len = (dst_len < src_len) ? dst_len : src_len;
    for (size_t i = 0; i < copy_len; ++i) {
        dst[i] = src[i];
    }
    return copy_len;
}
