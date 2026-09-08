; =====================================================================
; Script Inno Setup: Instalador Oficial da Linguagem Sotlas para Windows
; Produz o executavel: Sotlas-Setup-v0.2.0.exe
; =====================================================================

#define MyAppName "Sotlas Programming Language"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "Equipe Sotlas"
#define MyAppURL "https://github.com/HPinho/LangSotlas"
#define MyAppExeName "sotlas.cmd"

[Setup]
AppId={{D54A81E9-0B78-4F25-8FA3-6901A54397F1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Sotlas
DefaultGroupName=Sotlas
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=Sotlas-Setup-v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ChangesEnvironment=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "addtopath"; Description: "Adicionar diretório bin do Sotlas à variável de ambiente PATH do sistema"; GroupDescription: "Configurações do Sistema:"; Flags: checkedonce
Name: "assocfiles"; Description: "Associar arquivos de código-fonte .sotlas ao compilador Sotlas"; GroupDescription: "Associações de Arquivo:"; Flags: checkedonce
Name: "desktopicon"; Description: "Criar atalho do Sotlas Studio na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\..\dist\sotlas-v{#MyAppVersion}-windows-x64\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Sotlas REPL"; Filename: "cmd.exe"; Parameters: "/k ""{app}\bin\sotlas.cmd"" repl"; WorkingDir: "{userdocs}"
Name: "{group}\Sotlas Studio (Web IDE)"; Filename: "{app}\bin\sotlas.cmd"; Parameters: "studio"; WorkingDir: "{app}"
Name: "{group}\Desinstalar Sotlas"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Sotlas Studio"; Filename: "{app}\bin\sotlas.cmd"; Parameters: "studio"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; Registrar SOTLAS_HOME
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: string; ValueName: "SOTLAS_HOME"; ValueData: "{app}"; Flags: uninsdeletevalue
; Associacao de extensao .sotlas
Root: HKLM; Subkey: "Software\Classes\.sotlas"; ValueType: string; ValueName: ""; ValueData: "SotlasSourceFile"; Flags: uninsdeletevalue; Tasks: assocfiles
Root: HKLM; Subkey: "Software\Classes\SotlasSourceFile"; ValueType: string; ValueName: ""; ValueData: "Sotlas Source Code File"; Flags: uninsdeletekey; Tasks: assocfiles
Root: HKLM; Subkey: "Software\Classes\SotlasSourceFile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\assets\icon.ico,0"; Tasks: assocfiles
Root: HKLM; Subkey: "Software\Classes\SotlasSourceFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\bin\sotlas.cmd"" run ""%1"""; Tasks: assocfiles

[Code]
// Adicionar ao PATH do sistema
const EnvironmentKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

procedure CurStepChanged(CurStep: TSetupStep);
var
    Paths: string;
    BinDir: string;
begin
    if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
    begin
        BinDir := ExpandConstant('{app}\bin');
        if RegQueryStringValue(HKEY_LOCAL_MACHINE, EnvironmentKey, 'Path', Paths) then
        begin
            if Pos(BinDir, Paths) = 0 then
            begin
                Paths := Paths + ';' + BinDir;
                RegWriteStringValue(HKEY_LOCAL_MACHINE, EnvironmentKey, 'Path', Paths);
            end;
        end;
    end;
end;
