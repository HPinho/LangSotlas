#ifndef SOTLAS_RUNTIME_H
#define SOTLAS_RUNTIME_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Definições de ABI e cabeçalho de contagem de referências (ARC)
typedef struct {
    size_t ref_count;
    size_t data_size;
} SotlasArcHeader;

// Pânico freestanding
void sotlas_panic(const char *message);

// Inicialização e gerenciamento de ARC
void sotlas_arc_init(SotlasArcHeader *header, size_t size);
SotlasArcHeader *sotlas_arc_retain(SotlasArcHeader *header);
bool sotlas_arc_release(SotlasArcHeader *header);
size_t sotlas_arc_count(const SotlasArcHeader *header);

// Utilitários de memória freestanding (quando não compilado com libc)
void *sotlas_memset(void *dest, int val, size_t count);
void *sotlas_memcpy(void *dest, const void *src, size_t count);
int sotlas_memcmp(const void *s1, const void *s2, size_t count);

#ifdef __cplusplus
}
#endif

#endif // SOTLAS_RUNTIME_H
