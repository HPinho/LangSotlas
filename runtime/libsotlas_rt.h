/* libsotlas_rt.h — Standalone Freestanding Runtime para Sotlas.
 *
 * Provê a infraestrutura básica de execução sem depender de libc:
 * - Alocação de memória (bump allocator e hooks de heap)
 * - Contadores de referência automáticos (ARC)
 * - Manipulador de pânico
 * - Cópias seguras de fatias (slices)
 */
#ifndef LIBSOTLAS_RT_H
#define LIBSOTLAS_RT_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- ARC Header --- */
typedef struct {
    int64_t strong_count;
    int64_t weak_count;
} SotlasArcHeader;

/* --- Assinatura de Alocadores Customizáveis --- */
typedef void* (*SotlasAllocFn)(size_t size, size_t alignment);
typedef void  (*SotlasFreeFn)(void *ptr);

void sotlas_rt_set_allocator(SotlasAllocFn alloc_fn, SotlasFreeFn free_fn);

/* --- Alocação e Desalocação --- */
void* sotlas_rt_alloc(size_t size);
void* sotlas_rt_alloc_aligned(size_t size, size_t alignment);
void* sotlas_rt_realloc(void *ptr, size_t new_size);
void  sotlas_rt_free(void *ptr);

/* --- ARC (Automatic Reference Counting) --- */
void sotlas_rt_arc_retain(void *object);
void sotlas_rt_arc_release(void *object, void (*destructor)(void *));

/* --- Manipulador de Pânico --- */
typedef void (*SotlasPanicFn)(const char *message, const char *file, uint32_t line);
void sotlas_rt_set_panic_handler(SotlasPanicFn handler);
void sotlas_rt_panic(const char *message, const char *file, uint32_t line);

/* --- Fatias e Buffers Freestanding --- */
bool sotlas_rt_slice_eq(const uint8_t *a, size_t a_len, const uint8_t *b, size_t b_len);
size_t sotlas_rt_slice_copy(uint8_t *dst, size_t dst_len, const uint8_t *src, size_t src_len);

#ifdef __cplusplus
}
#endif

#endif /* LIBSOTLAS_RT_H */
