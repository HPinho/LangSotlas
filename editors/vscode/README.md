# Sotlas for Visual Studio Code

Extensao oficial de suporte para a linguagem de programacao de sistemas **Sotlas** (`.sotlas`, `.sth`).

---

## Recursos Principais

- **Realce de Sintaxe Completo**:
  - Palavras-chave de controle e fluxo: `discern`, `match`, `if`, `guard`, `defer`, etc.
  - Palavras-chave de declaracao e arquitetura: `forge`, `enclave`, `fn`, `trapfn`, `struct`, `mesh`, `barecore`.
  - Ponteiros de Topologia e Seguranca Fisica: `*rawphys`, `*virtmap`, `*portwire`, `*dmazone`, `*voidzero`.
  - Operadores de Registradores e Bits: `.slit[lo..hi]`, `.notch[n]`, `.strand[len]`.
  - Primitivas SRG & Concorrencia: `pulse`, `probe`, `clinch`, `rebound`, `quarantine`.
- **Servidor de Linguagem (LSP) Integrado**:
  - Diagnosticos em tempo real com verificacao de tipos e checagem de regras de hardware.
  - Autocompletar inteligente para instrucoes, registradores e funcoes da biblioteca base.
  - Informacoes de tipo e documentacao ao passar o mouse (*Hover*).
  - Formatacao automatica de codigo (*Format Document*).
  - Ir para Definicao (*Go to Definition*).
- **Ferramentas de Desenvolvimento e Comandos Integrados**:
  - `Sotlas: Compilar Pacote Atual` (`sotlas.build`)
  - `Sotlas: Verificar Tipos e Sintaxe` (`sotlas.check`)
  - `Sotlas: Formatar Arquivo Atual` (`sotlas.format`)
  - `Sotlas: Abrir Sotlas Studio (Navegador)` (`sotlas.studio`)
  - `Sotlas: Iniciar Terminal Interativo (REPL)` (`sotlas.repl`)
  - `Sotlas: Emitir WebAssembly (.wat)` (`sotlas.dumpWasm`)
  - `Sotlas: Reiniciar Servidor de Linguagem (LSP)` (`sotlas.restartServer`)

---

## Requisitos

Para que o LSP e os comandos funcionem, instale a toolchain do Sotlas e garanta que `sotlas` esteja acessivel no seu `PATH`:

```powershell
# No Windows (PowerShell):
irm https://raw.githubusercontent.com/HPinho/LangSotlas/main/packaging/install.ps1 | iex
```

```bash
# No Linux / macOS:
curl -fsSL https://raw.githubusercontent.com/HPinho/LangSotlas/main/packaging/install.sh | bash
```

---

## Configuracoes

| Configuracao | Padrao | Descricao |
| :--- | :--- | :--- |
| `sotlas.compilerPath` | `"sotlas"` | Caminho para o binario executavel do compilador Sotlas. |

---

## Empacotamento e Instalacao Local (.vsix)

Para gerar o pacote instalavel da extensao:

```bash
cd editors/vscode
npm install
npm run compile
npx @vscode/vsce package
```

Isto gera o arquivo `baken-sotlas-0.3.0.vsix`. Para instalar no seu VS Code imediatamente:

```bash
code --install-extension baken-sotlas-0.3.0.vsix
```

---

## Licenca

Distribuido sob a licenca Apache 2.0 com LLVM Exception.
Copyright (c) 2026 Hiago Pinho e contribuidores do projeto Sotlas.
