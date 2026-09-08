/**
 * Sotlas Stable C-ABI & Multi-Language Interoperability Specification (C / C++ / Objective-C)
 * 
 * Filosofia:
 * "Sotlas deve possuir uma ABI C estável e bidirecional, permitindo interoperabilidade
 * incremental com C, assembly, Objective-C e outras linguagens capazes de consumir C ABI,
 * mantendo toda memória externa e ponteiros FFI atrás de fronteiras explícitas unsafe."
 *
 * Arquitetura de 3 Camadas:
 *   [Sotlas Safe Layer]      (Objetos, Arrays, Optionals, UI, Aplicações)
 *            │
 *     explicit @system
 *            │
 *   [Sotlas Systems Layer]   (Ponteiros de topologia, MMIO, DMA, Interrupções)
 *            │
 *       extern "C"
 *            │
 *   [C / C++ / Objective-C]  (Fronteira externa não-gerenciada e explicitamente unsafe)
 */

#ifndef SOTLAS_ABI_H
#define SOTLAS_ABI_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
#define SOTLAS_EXTERN_C extern "C"
#define SOTLAS_NOEXCEPT noexcept
#else
#define SOTLAS_EXTERN_C extern
#define SOTLAS_NOEXCEPT
#endif

#if defined(_WIN32) || defined(__CYGWIN__)
    #define SOTLAS_EXPORT __declspec(dllexport)
    #define SOTLAS_IMPORT __declspec(dllimport)
#elif defined(__GNUC__) || defined(__clang__)
    #define SOTLAS_EXPORT __attribute__((visibility("default")))
    #define SOTLAS_IMPORT
#else
    #define SOTLAS_EXPORT
    #define SOTLAS_IMPORT
#endif

/* ---------------------------------------------------------------------------
 * Anotações de Fronteira e Documentação Semântica FFI
 * --------------------------------------------------------------------------- */

/**
 * Marca um ponteiro de origem externa cuja posse e tempo de vida
 * NÃO são conhecidos nem gerenciados pelo compilador Sotlas.
 */
#define SOTLAS_FOREIGN_PTR

/**
 * Delimita uma função que atua como fronteira FFI estrita, exigindo
 * encapsulamento em bloco unsafe no ponto de chamada em Sotlas.
 */
#define SOTLAS_UNSAFE_BOUNDARY

/* ---------------------------------------------------------------------------
 * Representações Binárias Estáveis (C-ABI)
 * --------------------------------------------------------------------------- */

/**
 * Fatias de Memória FFI (Slice estável em C ABI)
 */
typedef struct {
    const uint8_t *data;
    size_t len;
} SotlasByteSlice;

typedef struct {
    uint8_t *data;
    size_t len;
} SotlasMutByteSlice;

/**
 * Representação estável C ABI para Option<T>
 */
typedef struct {
    bool has_value;
    uint32_t value;
} SotlasOptionU32;

typedef struct {
    bool has_value;
    uint64_t value;
} SotlasOptionU64;

typedef struct {
    bool has_value;
    void *ptr;
} SotlasOptionPtr;

/**
 * Representação estável C ABI para Result<T, E>
 */
typedef struct {
    int32_t status;  /* 0 = OK, negativo/positivo = código de erro */
    uint64_t value;
} SotlasResultU64;

/* ---------------------------------------------------------------------------
 * Ponteiros de Topologia Físico-Semântica em C/C++
 * --------------------------------------------------------------------------- */

#define sotlas_rawphys  volatile uint8_t*
#define sotlas_virtmap  uint8_t*
#define sotlas_portwire volatile uint16_t*
#define sotlas_dmazone  uint8_t* __attribute__((aligned(64)))

/* ---------------------------------------------------------------------------
 * Shims de Interoperabilidade com Objective-C (sem overhead do runtime no kernel)
 * --------------------------------------------------------------------------- */

#ifdef __OBJC__
    #import <objc/runtime.h>
    #import <objc/message.h>
#else
    typedef void *sotlas_objc_id;
    typedef void *sotlas_objc_sel;
    typedef void *sotlas_objc_class;
#endif

/**
 * Função de ponte para invocar despachos Objective-C com fronteira C ABI pura,
 * garantindo que falhas de nil e chamadas dinâmicas permaneçam isoladas.
 */
SOTLAS_EXTERN_C SOTLAS_EXPORT SOTLAS_UNSAFE_BOUNDARY
void *sotlas_objc_msg_send_bridge(void *receiver, void *selector, void *arg);

#endif /* SOTLAS_ABI_H */
