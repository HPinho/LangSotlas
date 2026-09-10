@echo off
setlocal

echo =======================================================
echo   Sotlas Native Compiler Autonomous Build (Zero-Python)
echo =======================================================

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

if not exist "build" mkdir "build"
if not exist "bin" mkdir "bin"

rem 1. Localizar compilador C
set "CC="
where clang >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "CC=clang"
    goto :FOUND_CC
)
if exist "C:\Program Files\LLVM\bin\clang.exe" (
    set "CC=C:\Program Files\LLVM\bin\clang.exe"
    goto :FOUND_CC
)
where gcc >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "CC=gcc"
    goto :FOUND_CC
)

echo [ERRO] Nenhum compilador C encontrado.
exit /b 1

:FOUND_CC
echo [OK] Compilador C detectado: %CC%

rem 2. Verificar se ja existe o binario nativo
if exist "bin\sotlas_native.exe" (
    echo [INFO] Binario nativo existente detectado em bin\sotlas_native.exe
    echo [INFO] Executando auto-compilacao nativa direta (Zero-Python)
    "bin\sotlas_native.exe" "bootstrap\sotlas\sotlas_lite\main.sotlas" -o "build\sotlas_compiler_stage2.c"
    if %ERRORLEVEL% equ 0 (
        "%CC%" -O2 "build\sotlas_compiler_stage2.c" "bootstrap\sotlas\sotlas_lite\sotlas_native_driver.c" -o "bin\sotlas_native.exe"
        if %ERRORLEVEL% equ 0 (
            echo [SUCESSO] Compilador nativo atualizado com sucesso via auto-compilacao nativa!
            "bin\sotlas_native.exe" --version
            exit /b 0
        )
    )
)

echo [INFO] Gerando compilador nativo inicial via bootstrap pipeline
python -c "import sys; from pathlib import Path; sys.path.insert(0, 'compiler'); from sotlas.bootstrap_pipeline import build_self_hosted_compiler; build_self_hosted_compiler(Path('bin/sotlas_native.exe'))"
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Falha ao gerar o compilador inicial
    exit /b 1
)

echo [INFO] Validando auto-compilacao nativa de Stage 2 via sotlas_native.exe
"bin\sotlas_native.exe" "bootstrap\sotlas\sotlas_lite\main.sotlas" -o "build\sotlas_compiler_stage2.c"
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Falha na auto-compilacao nativa de Stage 2
    exit /b 1
)

echo [SUCESSO] Compilador nativo Sotlas pronto e verificado: bin\sotlas_native.exe
"bin\sotlas_native.exe" --version
exit /b 0
