#!/usr/bin/env bash
# ==============================================================================
# Instalador Automatizado da Linguagem Sotlas para Linux e macOS
# ==============================================================================
# Uso:
#   curl -fsSL https://sotlas.org/install.sh | bash
# Ou localmente:
#   bash packaging/install.sh
# ==============================================================================

set -e

INSTALL_DIR="${SOTLAS_INSTALL_DIR:-$HOME/.sotlas}"
BIN_DIR="$INSTALL_DIR/bin"

echo ""
echo "==================================================================="
echo "              INSTALADOR DA LINGUAGEM SOTLAS                       "
echo "     Segura por padrão, desculpadamente orientada a sistemas       "
echo "==================================================================="
echo ""

echo "-> Diretório de destino: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -d "$REPO_ROOT/dist/sotlas-v0.2.0-linux-x64" ]; then
    echo "-> Instalando a partir do pacote construído..."
    cp -R "$REPO_ROOT/dist/sotlas-v0.2.0-linux-x64/"* "$INSTALL_DIR/"
else
    echo "-> Gerando bundle de produção local..."
    python3 "$SCRIPT_DIR/package.py" --target linux || python "$SCRIPT_DIR/package.py" --target linux
    cp -R "$REPO_ROOT/dist/sotlas-v0.2.0-linux-x64/"* "$INSTALL_DIR/"
fi

chmod +x "$BIN_DIR"/* 2>/dev/null || true

# Configurar PATH em ~/.bashrc e ~/.zshrc
PATH_LINE="export PATH=\"$BIN_DIR:\$PATH\""
SOTLAS_HOME_LINE="export SOTLAS_HOME=\"$INSTALL_DIR\""

for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [ -f "$RC" ]; then
        if ! grep -q "SOTLAS_HOME" "$RC"; then
            echo "" >> "$RC"
            echo "# Sotlas Toolchain" >> "$RC"
            echo "$SOTLAS_HOME_LINE" >> "$RC"
            echo "$PATH_LINE" >> "$RC"
            echo "-> Atualizado: $RC"
        fi
    fi
done

echo ""
echo "==================================================================="
echo "          LINGUAGEM SOTLAS INSTALADA COM SUCESSO!                  "
echo "==================================================================="
echo ""
echo "Comandos disponíveis:"
echo "  sotlas --help           # Exibe ajuda e comandos"
echo "  sotlas repl             # Abre o terminal interativo (REPL)"
echo "  sotlas studio           # Inicia o Web Studio Playground"
echo "  sotlas dump-wasm <file> # Emite WebAssembly direto (sem C)"
echo ""
echo "Reinicie sua sessão de terminal ou execute:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
echo "  sotlas version"
echo ""
