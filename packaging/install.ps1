# ==============================================================================
# Instalador Automatizado da Linguagem Sotlas para Windows (PowerShell)
# ==============================================================================
# Uso rápido:
#   powershell -ExecutionPolicy Bypass -File .\packaging\install.ps1
# Ou via One-Liner na Web:
#   irm https://sotlas.org/install.ps1 | iex
# ==============================================================================

param (
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\Sotlas",
    [string]$SourceZip = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host " =================================================================== " -ForegroundColor Cyan
Write-Host "                INSTALADOR DA LINGUAGEM SOTLAS                       " -ForegroundColor White
Write-Host "       Segura por padrao, desculpadamente orientada a sistemas       " -ForegroundColor Gray
Write-Host " =================================================================== " -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

# 1. Definir diretorio de instalacao
Write-Host "-> Diretorio de destino: $InstallDir" -ForegroundColor Yellow
if (Test-Path $InstallDir) {
    if ($Force) {
        Write-Host "   Removendo instalacao anterior (-Force)..." -ForegroundColor DarkGray
        Remove-Item -Path $InstallDir -Recurse -Force
    } else {
        Write-Host "   Atualizando instalacao existente..." -ForegroundColor DarkGray
    }
}
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# 2. Copiar / Extrair componentes
if ($SourceZip -and (Test-Path $SourceZip)) {
    Write-Host "-> Extraindo pacote $SourceZip..." -ForegroundColor Green
    Expand-Archive -Path $SourceZip -DestinationPath $InstallDir -Force
} else {
    Write-Host "-> Instalando toolchain a partir do repositorio local..." -ForegroundColor Green
    
    # Executar o gerador de bundle se necessario
    $BundlePath = "$RepoRoot\dist\sotlas-v0.2.0-windows-x64"
    if (-not (Test-Path $BundlePath)) {
        Write-Host "   Gerando bundle de producao..." -ForegroundColor DarkGray
        py "$ScriptDir\package.py" --target windows
    }

    # Copiar conteudo do bundle para $InstallDir
    Copy-Item -Path "$BundlePath\*" -Destination $InstallDir -Recurse -Force
}

# 3. Adicionar ao PATH do Usuario
$BinDir = "$InstallDir\bin"
Write-Host "-> Configurando variaveis de ambiente..." -ForegroundColor Green

[Environment]::SetEnvironmentVariable("SOTLAS_HOME", $InstallDir, [EnvironmentVariableTarget]::User)
$env:SOTLAS_HOME = $InstallDir

$UserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
if ($UserPath -notlike "*$BinDir*") {
    $NewPath = "$BinDir;$UserPath"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, [EnvironmentVariableTarget]::User)
    $env:Path = "$BinDir;$env:Path"
    Write-Host "   Adicionado '$BinDir' ao PATH do usuario." -ForegroundColor Cyan
} else {
    Write-Host "   '$BinDir' ja esta presente no PATH." -ForegroundColor DarkGray
}

# 4. Associar extensao .sotlas no Windows Registry (HKCU)
try {
    New-Item -Path "HKCU:\Software\Classes\.sotlas" -Value "SotlasSourceFile" -Force | Out-Null
    New-Item -Path "HKCU:\Software\Classes\SotlasSourceFile" -Value "Sotlas Source File" -Force | Out-Null
    New-Item -Path "HKCU:\Software\Classes\SotlasSourceFile\shell\open\command" -Value "`"$BinDir\sotlas.cmd`" run `"%1`"" -Force | Out-Null
    Write-Host "   Extensao .sotlas associada com sucesso ao driver sotlas." -ForegroundColor Cyan
} catch {
    Write-Host "   Aviso: nao foi possivel registrar a extensao .sotlas (sem impacto no compilador)." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host " =================================================================== " -ForegroundColor Green
Write-Host "           LINGUAGEM SOTLAS INSTALADA COM SUCESSO!                   " -ForegroundColor White
Write-Host " =================================================================== " -ForegroundColor Green
Write-Host ""
Write-Host "Comandos disponiveis no seu terminal:" -ForegroundColor Yellow
Write-Host "  sotlas --help           # Exibe ajuda e comandos" -ForegroundColor White
Write-Host "  sotlas repl             # Abre o terminal interativo (REPL)" -ForegroundColor White
Write-Host "  sotlas studio           # Abre o Web Studio Playground no navegador" -ForegroundColor White
Write-Host "  sotlas dump-wasm <file> # Emite WebAssembly sem C" -ForegroundColor White
Write-Host "  sotlas new <projeto>    # Cria um novo pacote de sistemas" -ForegroundColor White
Write-Host ""
Write-Host "Reinicie seu terminal para carregar o novo PATH, ou teste agora:" -ForegroundColor DarkGray
Write-Host "& `"$BinDir\sotlas.cmd`" version" -ForegroundColor Cyan
Write-Host ""
