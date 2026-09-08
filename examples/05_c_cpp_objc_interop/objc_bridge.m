/**
 * Objective-C Bridge: Demonstra a interoperabilidade segura com Objective-C.
 *
 * Filosofia:
 * Sotlas interage com Objective-C usando a ABI C como fronteira estrita.
 * Isso evita a propagação de 'nil-messaging' e tipagem permissiva para o kernel
 * e para a camada segura de Sotlas.
 */
#import <Foundation/Foundation.h>
#include <stdint.h>
#include "../../include/sotlas/sotlas_abi.h"

// Função exportada por Sotlas
SOTLAS_EXTERN_C uint32_t sotlas_entry_process(uint32_t channel);

@interface LegacyDeviceController : NSObject
- (uint32_t)runDiagnosticOnChannel:(uint32_t)channel;
@end

@implementation LegacyDeviceController

- (uint32_t)runDiagnosticOnChannel:(uint32_t)channel {
    NSLog(@"[Obj-C] Delegando processamento de alta performance para Sotlas...");
    // Chamada direta através da ABI C estável — sem custo de objc_msgSend
    uint32_t status = sotlas_entry_process(channel);
    NSLog(@"[Obj-C] Processamento concluído pelo Sotlas. Status: %u", status);
    return status;
}

@end
