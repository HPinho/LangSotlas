/**
 * C Consumer: Exemplo de código C/C++ consumindo e fornecendo APIs para Sotlas
 * através da ABI C estável e bidirecional.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "../../include/sotlas/sotlas_abi.h"

// Função em Sotlas exportada via C ABI
SOTLAS_EXTERN_C uint32_t sotlas_entry_process(uint32_t channel);

// Função em C fornecida para Sotlas
static uint8_t g_device_buffer[64] = { 0x42, 0x01, 0x02, 0x03 };

SOTLAS_EXTERN_C SOTLAS_UNSAFE_BOUNDARY
uint8_t *legacy_device_read(uint32_t channel, size_t *out_len) {
    if (out_len) {
        *out_len = sizeof(g_device_buffer);
    }
    printf("[C Host] Canal %u lido via C ABI legada.\n", channel);
    return g_device_buffer;
}

SOTLAS_EXTERN_C SOTLAS_UNSAFE_BOUNDARY
void legacy_notify_host(int32_t code) {
    printf("[C Host] Notificação recebida do Sotlas com código: %d\n", code);
}

int main(void) {
    printf("[C Host] Chamando módulo Sotlas...\n");
    uint32_t result = sotlas_entry_process(1);
    printf("[C Host] Resultado retornado pelo Sotlas: %u\n", result);
    return 0;
}
