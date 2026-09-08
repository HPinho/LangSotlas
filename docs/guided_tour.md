# A Guided Tour of Sotlas

Bem-vindo ao tour guiado da linguagem **Sotlas**. Projetada para superar as lacunas históricas de segurança, modularidade e controle deixadas pelo C, C++ e Objective-C, Sotlas foi construída sob o princípio:
> *"Segura por padrão, assumidamente capaz de sistemas."*

---

## 1. Valores Simples: Imutabilidade por Padrão

Diferente do C, onde a mutabilidade descontrolada e ponteiros crus são fontes contínuas de bugs, em Sotlas as variáveis são imutáveis por padrão para garantir previsibilidade e ausência de efeitos colaterais acidentais.

```sotlas
// Declaração imutável
let pi: f32 = 3.14159;
let message = "Olá, Sotlas!";

// Declaração mutável explícita
let mut counter: u32 = 0;
counter = counter + 1;
```

---

## 2. Estruturas de Dados e Classes (Valor vs Referência)

Enquanto o C++ impõe complexidade de cópias e o Objective-C força quase tudo para alocação dinâmica com sobrecarga de runtime, Sotlas oferece uma separação cristalina:

### 2.1. Structs (Semântica de Valor Zero-Cost)

Structs em Sotlas têm semântica de valor pura, sendo alocadas no stack ou incorporadas diretamente em outras estruturas sem custos ocultos de alocação:

```sotlas
pub struct Point {
    pub x: i32;
    pub y: i32;
}

let pt: Point = Point { x: 10, y: 20 };
```

### 2.2. Classes com Métodos e ARC (Semântica de Referência Previsível)

Classes são gerenciadas por contagem automática de referências (ARC) estrita e previsível, sem o overhead de despacho dinâmico de mensagens (`objc_msgSend`) do Objective-C e sem os riscos de destruidores não-determinísticos de C++:

```sotlas
pub class Window {
    title_hash: u64;
    width: u32;
    height: u32;

    pub fn new(w: u32, h: u32) -> Window {
        let mut win: Window = 0;
        win.width = w;
        win.height = h;
        return win;
    }

    pub fn area(self: *const Window) -> u32 {
        unsafe {
            return self.width * self.height;
        }
    }
}
```

---

## 3. Tratamento Seguro de Erros: `Option` e `Result`

No C e Objective-C, ponteiros nulos (`NULL`/`nil`) e retornos manuais de inteiros de erro causam falhas silenciosas ou travamentos súbitos (*null pointer dereference*). Em Sotlas, o compilador exige tratamento explícito via tipos da `stdlib/core`:

```sotlas
import core::option::*;
import core::result::*;

pub fn find_device(bus_id: u32) -> OptionU32 {
    if bus_id == 0 {
        return OptionU32::some(0x10DE);
    }
    return OptionU32::none();
}

pub fn allocate_pages(count: usize) -> ResultU32 {
    if count > 1024 {
        return ResultU32::err(ResultCode::OutOfMemory);
    }
    return ResultU32::ok(count as u32);
}
```

---

## 4. O Modelo de Efeitos: `@system` vs `unsafe`

Uma das maiores inovações de Sotlas para programação de sistemas operacionais e bare-metal é a distinção ortogonal entre **privilégio de hardware** e **manipulação de memória**:

- **`@system`**: Concede acesso a **capacidades privilegiadas de hardware** (portas I/O como `inb`/`outb`, registradores de controle `CR0-4`, tabelas de páginas, instruções de interrupção `cli`/`sti`). Código comum não pode invocar funções `@system` sem auditoria explícita.
- **`unsafe { ... }`**: Delimita escopos léxicos estritos para operações em **ponteiros crus** (`*mut T`, `*const T`) e desreferenciamento de memória.

```sotlas
module kernel::driver::serial;
import system::intrinsics::*;

const COM1_PORT: u16 = 0x3F8;

@system
pub fn serial_write_byte(b: u8) {
    // Escrita direta em porta de hardware
    outb(COM1_PORT, b);
}

pub fn write_memory_buffer(dest: *mut u8, offset: usize, val: u8) {
    unsafe {
        dest[offset] = val;
    }
}
```

---

## 5. Resolução Modular do Kernel (Sem `#include`)

O sistema de compilação em C e C++ depende de inclusões de cabeçalhos (`#include`), gerando tempos de compilação excessivos e vulnerabilidades de pré-processador. Em Sotlas, módulos são entidades de primeira classe com namespaces bem definidos:

```sotlas
module kernel::scheduler::core;

import kernel::sync::spinlock::*;
import kernel::arch::x86_64::smp::*;

pub fn schedule_next_task() {
    // Coordenação entre subsistemas sem poluição de macros
}
```

---

## 6. Ferramental de Linha de Comando (CLI)

O driver `sotlas` disponibiliza comandos integrados e unificados para desenvolvimento moderno:

```bash
# Verificar sintaxe, tipos e safety sem emitir código
sotlas check main.sotlas

# Inspecionar a AST
sotlas dump-ast main.sotlas

# Inspecionar as instruções intermediárias SSA (SIR)
sotlas dump-sir main.sotlas

# Compilar para C11 ou objeto de kernel freestanding
sotlas compile main.sotlas --target x86_64-freestanding

# Executar a suíte completa de testes
sotlas test
```
