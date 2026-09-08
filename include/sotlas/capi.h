#ifndef SOTLAS_CAPI_H
#define SOTLAS_CAPI_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SOTLAS_VERSION_MAJOR 0
#define SOTLAS_VERSION_MINOR 2
#define SOTLAS_VERSION_PATCH 0
#define SOTLAS_VERSION_STRING "0.2.0"

// Status de execução do compilador e ferramentas
typedef enum {
    SOTLAS_SUCCESS = 0,
    SOTLAS_ERROR_GENERIC = 1,
    SOTLAS_ERROR_LEX = 2,
    SOTLAS_ERROR_PARSE = 3,
    SOTLAS_ERROR_SEMA = 4,
    SOTLAS_ERROR_SAFETY = 5,
    SOTLAS_ERROR_CODEGEN = 6
} SotlasStatus;

const char *sotlas_get_version(void);

#ifdef __cplusplus
}
#endif

#endif // SOTLAS_CAPI_H
