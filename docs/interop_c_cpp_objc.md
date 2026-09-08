# Interoperabilidade com C, C++ e Objective-C em Sotlas

## 1. Visão Filosófica e Objetivo Formal

> **Objetivo Formal de Interoperabilidade:**
> *"Sotlas deve possuir uma ABI C estável e bidirecional, permitindo interoperabilidade incremental com C, assembly, Objective-C e outras linguagens capazes de consumir C ABI, mantendo toda memória externa e ponteiros FFI atrás de fronteiras explícitas unsafe."*

Historicamente, linguagens de sistemas enfrentam um dilema:
- **C e Objective-C**: Altamente interoperáveis, mas perigosamente permissivos. Em Objective-C tradicional, qualquer ponteiro pode ser manipulado sem guardrails, conversões implícitas são toleradas e o *nil-messaging* esconde falhas catastróficas em tempo de execução.
- **C++**: Tenta adicionar abstrações, mas introduz um custo proibitivo para kernels e sistemas bare-metal: mangling complexo e instável entre versões de compiladores, exceções invisíveis, RTTI pesado e destruidores implícitos que quebram garantias determinísticas de tempo real.

Sotlas resolve esse dilema combinando a tríade:
1. **Ergonomia Moderna**: Expressividade intuitiva, tipos algébricos (`Option`, `Result`), fatias seguras (`Slice`), inferência estrita e contracts (`spec`/`adopts`).
2. **Fronteiras `unsafe` Explícitas no Estilo Rust**: O compilador assume que não conhece a proveniência, validade ou tempo de vida de nenhum ponteiro externo. Qualquer manipulação de memória crua exige a palavra-chave `unsafe { ... }`.
3. **Acesso Direto no Estilo C**: Sem overhead de runtime, sem garbage collector, e com despacho determinístico compatível com a ABI C padrão de mercado.

---

## 2. A Arquitetura de 3 Camadas de Sotlas

Para garantir que o código de aplicação permaneça inviolável enquanto o kernel se comunica com hardware e bibliotecas legadas, Sotlas organiza o software em **3 camadas ortogonais**:

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

### O Pipeline da Fronteira Perigosa
```text
Objective-C / C / C++ ──► [Unsafe Boundary] ──► Sotlas Systems ──► [Safe Abstractions] ──► Sotlas Safe Layer
```

1. **Memória Não-Confiável**: Dados vindos de C, C++ ou Objective-C entram no sistema como ponteiros estrangeiros não-gerenciados.
2. **Fronteira Insegura (`unsafe`)**: A camada de sistemas (`@system`) de Sotlas recebe esses ponteiros dentro de blocos `unsafe { ... }`, valida limites e alinhamento.
3. **Abstração Segura**: O ponteiro é imediatamente empacotado em tipos seguros (`Option<T>`, `Result<T, E>`, `ByteSlice` ou structs com validação).
4. **Camada Segura de Aplicação**: A UI, o renderizador e as aplicações consomem apenas tipos seguros, livres de risco de corrupção de memória ou *buffer overflows*.

---

## 3. Guardrails de `unsafe` em Sotlas

### 3.1. Proibição de Casts e Desreferenciamento Implícito
Fora de um bloco `unsafe { ... }`, o seguinte código é **terminantemente rejeitado pelo compilador**:

```sotlas
// ERRO DE COMPILAÇÃO: criação/conversão para ponteiro cru exige bloco unsafe explícito
let ptr: *mut u32 = 0xDEADBEEF as *mut u32;

// ERRO DE COMPILAÇÃO: desreferenciamento de ponteiro cru exige bloco unsafe explícito
*ptr = 42;
```

A linguagem exige intenção explícita do engenheiro:

```sotlas
unsafe {
    let ptr: *mut u32 = 0xDEADBEEF as *mut u32;
    *ptr = 42;
}
```

### 3.2. Marcação Explícita de Risco em `extern "C"`
Em Sotlas, declarar uma função externa indica que o compilador não pode auditar sua segurança:

```sotlas
extern "C" {
    // A anotação unsafe fn documenta no contrato que a chamada é perigosa
    unsafe fn driver_map_mmio(base: u64) -> *mut u8;
}
```

Chamadas a essa função exigem `unsafe`:

```sotlas
@system
fn initialize_driver(base: u64) -> SafeDeviceHandle {
    let raw_addr: *mut u8 = unsafe {
        driver_map_mmio(base)
    };
    return SafeDeviceHandle::new(raw_addr);
}
```

---

## 4. Integração com Linguagens Específicas

### 4.1. Interoperabilidade com C Puro
- **Importação**: `extern "C" fn foo(x: u32) -> i32;` gera protótipo `extern int32_t foo(uint32_t x);`.
- **Exportação**: `@export pub fn sotlas_calc(x: u32) -> u32` é emitido com símbolo C não-mangled `uint32_t sotlas_calc(uint32_t x);`.
- **Layout de Dados**: Use `mesh` para alinhamento físico por campo ou structs padrão compatíveis com a representação em C11.

### 4.2. Interoperabilidade com C++
C++ consome Sotlas e fornece APIs para Sotlas através de linkage `extern "C"`:

```cpp
// Em C++
#include "sotlas/sotlas_abi.h"

extern "C" {
    void cpp_render_scene(const SotlasByteSlice* buffer);
    uint32_t sotlas_entry_process(uint32_t channel);
}

void invoke_sotlas() {
    uint32_t status = sotlas_entry_process(1);
}
```

Isso evita colisões de mangling entre diferentes compiladores C++ (GCC, Clang, MSVC) e garante que exceções C++ não vazem para dentro do kernel Sotlas.

### 4.3. Interoperabilidade com Objective-C (sem os Defeitos de Objective-C)
Em sistemas que interagem com runtimes derivados da Apple ou NeXTSTEP/GNUStep, Sotlas interage com Objective-C através de **bridges C ABI**:

1. **Sem Despacho Dinâmico Cego no Kernel**: Sotlas não utiliza `objc_msgSend` internamente em suas rotinas críticas de kernel ou renderização, evitando a penalidade de lookups de seletores em hash tables.
2. **Sem Falhas Silenciosas em Nil**: Em Objective-C, enviar uma mensagem para um ponteiro nulo (`nil`) retorna `0` silenciosamente, mascarando ponteiros corrompidos. Em Sotlas, ponteiros externos nulos são explicitamente verificados ou mapeados para `OptionPtr::none()`.
3. **Bridge Bidirecional Estável**:
   O arquivo [`include/sotlas/sotlas_abi.h`](file:///c:/Projetos/LangSotlas/include/sotlas/sotlas_abi.h) fornece wrappers C puros para instanciar e receber chamadas de classes Objective-C:

```objc
// Em Objective-C
#import "sotlas/sotlas_abi.h"

@implementation DeviceController
- (void)syncWithSotlas {
    // Invoca rotina de alta performance de Sotlas via C ABI direta
    uint32_t res = sotlas_entry_process(42);
}
@end
```

---

## 5. Resumo das Garantias

| Característica | C Tradicional | Objective-C | C++ | Sotlas (Estágio 0/1) |
| :--- | :---: | :---: | :---: | :---: |
| **ABI Estável** | Sim (C ABI) | Sim (Obj-C Runtime) | Instável (Mangling) | **Sim (ABI C Estável e Bidirecional)** |
| **Fronteiras `unsafe` Explícitas** | Não | Não | Não | **Sim (Estilo Rust)** |
| **Casts de Ponteiros Protegidos** | Não | Não | Não (`reinterpret_cast`) | **Sim (Exige `unsafe { ... }`)** |
| **Overhead de Nil-Messaging** | N/A | Alto (`objc_msgSend`) | N/A | **Zero (Tipos Algébricos `Option`)** |
| **Conformidade Freestanding / Kernel** | Sim | Difícil | Complexo | **Nativo (`barecore;`, `@system`)** |
