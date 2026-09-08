# Exemplo 05: Interoperabilidade C / C++ / Objective-C com Fronteiras Unsafe Estritas

Este exemplo demonstra a **arquitetura de interoperabilidade de 3 camadas** de Sotlas, concebida para integrar incrementalmente bases de código em C, C++ e Objective-C sem adotar o modelo excessivamente permissivo de linguagens legadas.

---

## 1. Filosofia: Guardrails Estritos sem Isolamento

> *"Sotlas deve possuir uma ABI C estável e bidirecional, permitindo interoperabilidade incremental com C, assembly, Objective-C e outras linguagens capazes de consumir C ABI, mantendo toda memória externa e ponteiros FFI atrás de fronteiras explícitas unsafe."*

Ao contrário do Objective-C tradicional (onde qualquer ponteiro pode ser manipulado sem guardrails e mensagens para `nil` falham silenciosamente), Sotlas impõe:

1. **Ergonomia Moderna**: tipos algébricos (`Option`, `Result`), fatias seguras (`Slice`), inferência estrita (`let`, `let mut`) e contratos explícitos.
2. **Fronteiras `unsafe` no estilo Rust**:
   - Cast de inteiro para ponteiro cru (`0xDEADBEEF as *mut u32`) é **proibido fora de `unsafe`**.
   - Desreferenciamento (`*ptr`) e indexação de ponteiro cru (`ptr[i]`) são **proibidos fora de `unsafe`**.
   - Chamadas a funções externas `extern "C"` que manipulam ponteiros crus são tratadas como **fronteiras de risco não-gerenciadas**.
3. **Acesso Direto no Estilo C**:
   - Zero sobrecarga de runtime.
   - Zero garbage collection no kernel/drivers.
   - ABI C padrão, estável e bidirecional.

---

## 2. Diagrama de Arquitetura de 3 Camadas

```text
                ┌──────────────────────────────────────┐
                │          Sotlas Safe Layer           │
                │ Objects / Arrays / Optionals / UI    │
                │ Totalmente segura e sem ponteiros crus│
                └──────────────────┬───────────────────┘
                                   │
                           explicit @system
                                   │
                ┌──────────────────▼───────────────────┐
                │        Sotlas Systems Layer          │
                │ Pointers / MMIO / DMA / Interrupts   │
                │ Isolamento de hardware do BakenOS    │
                └──────────────────┬───────────────────┘
                                   │
                              extern "C"
                                   │
            ┌──────────────────────▼──────────────────────┐
            │       C / C++ (extern "C") / Objective-C    │
            │          Assembly & Firmware                │
            │ Memória externa não confiável (unsafe)      │
            └─────────────────────────────────────────────┘
```

---

## 3. Fluxo de Dados: Da Memória Externa às Abstrações Seguras

```text
Objective-C / C / C++ ──► [Unsafe Boundary] ──► Sotlas Systems ──► [Safe Abstractions] ──► Sotlas Safe Layer
```

1. **C / Objective-C Host**:
   Fornece uma rotina legada via C ABI (`legacy_device_read`).
2. **Sotlas Systems Layer (`@system`)**:
   Chama a função externa dentro de `unsafe { ... }`, valida se o ponteiro não é nulo e converte o buffer bruto em uma estrutura segura (`SafePacket`).
3. **Sotlas Safe Layer**:
   Consome o pacote sem nenhum ponteiro cru ou palavra-chave `unsafe`, com segurança total de memória e bounds checking.
4. **Exportação Bidirecional**:
   A função `@export pub fn sotlas_entry_process` é gerada com símbolo C puro (`extern uint32_t sotlas_entry_process(uint32_t channel);`), podendo ser consumida diretamente por bibliotecas C, C++ (`extern "C"`) ou classes Objective-C (`objc_msgSend`).

---

## 4. Arquivos do Exemplo

- [`main.sotlas`](main.sotlas): Código-fonte Sotlas demonstrando as 3 camadas e exportação C ABI.
- [`c_consumer.c`](c_consumer.c): Consumidor e provedor C demonstrando a ponte bidirecional.
- [`objc_bridge.m`](objc_bridge.m): Bridge em Objective-C mostrando como chamar Sotlas sem propagar nil-messaging ao kernel.
- [`../../include/sotlas/sotlas_abi.h`](../../include/sotlas/sotlas_abi.h): Contratos e cabeçalhos de interoperabilidade C/C++/Obj-C.
