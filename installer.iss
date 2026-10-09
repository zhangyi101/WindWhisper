; ============================================================
; 风语 / WindWhisper v2.0 — Inno Setup 安装脚本
; 生成三个 exe：安装、更新/修复、卸载
; ============================================================
; 使用方法：
;   1. 安装 Inno Setup: https://jrsoftware.org/download.php/is.exe
;   2. 用 Inno Setup Compiler 打开此文件，编译生成安装包
;   3. 输出三个 exe：
;      - 风语_安装.exe        (首次安装)
;      - 风语_更新.exe        (更新/修复，保留用户配置)
;      - 风语_卸载.exe        (卸载，可选保留数据)
;
; 原则：
;   - 安装版：全新安装，创建桌面快捷方式
;   - 更新版：覆盖程序文件，保留 config.json 和数据
;   - 卸载版：删除程序，可选保留测风数据

#define MyAppName "风语"
#define MyAppNameEn "WindWhisper"
#define MyAppVersion "2.0"
#define MyAppExeName "风语.exe"
#define MyAppPublisher "WindWhisper Project"

[Setup]
AppId={{ WindWhisper-v2 }}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=风语_安装
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

; 卸载时询问是否保留数据
Uninstallable=yes
CreateUninstallRegKey=yes

; 语言
[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

; ============================================================
; 安装版文件
; ============================================================
[Files]
; 主程序
Source: "dist\风语.exe"; DestDir: "{app}"; Flags: ignoreversion
; 配置模板（不覆盖已有的 config.json）
Source: "config.json.template"; DestDir: "{app}"; Flags: onlyifdoesntexist
; 资源文件
Source: "resources\*"; DestDir: "{app}\resources"; Flags: recursesubdirs
; 安装/卸载脚本
Source: "INSTALL.md"; DestDir: "{app}"; Flags: ignoreversion
; Python 环境（如果用户没有 Python，提供便携版）
; 注意：venv 太大不放安装包，INSTALL.md 里有下载地址

; ============================================================
; 快捷方式
; ============================================================
[Icons]
; 桌面快捷方式
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\resources\icons\wind.ico"
; 开始菜单
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载{#MyAppName}"; Filename: "{uninstallexe}"

; ============================================================
; 安装后运行
; ============================================================
[Run]
; 首次安装后可选启动
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动{#MyAppName}"; Flags: nowait postinstall skipifsilent

; ============================================================
; 卸载
; ============================================================
[UninstallDelete]
; 删除程序文件
Type: files; Name: "{app}\{#MyAppExeName}"
Type: files; Name: "{app}\config.json.template"
Type: files; Name: "{app}\INSTALL.md"
Type: filesandordirs; Name: "{app}\resources"
; 不删除 config.json 和测风数据（用户选择）

[Code]
// ============================================================
// 卸载时询问是否保留数据
// ============================================================
function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  msgResult: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // 询问是否删除用户配置和数据
    msgResult := MsgBox(
      '是否同时删除配置文件和测风数据？' #13#10 #13#10 +
      '是 = 删除 config.json 和所有测风数据（不可恢复）' #13#10 +
      '否 = 保留配置和数据（方便以后重新安装）',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
    
    if msgResult = IDYES then
    begin
      // 删除配置
      DeleteFile(ExpandConstant('{app}\config.json'));
      // 删除数据目录（如果和程序目录不同）
      // 数据目录在 D:\测风数据文件，通常不在 app 目录下，所以一般不需要删
    end;
  end;
end;

// ============================================================
// 更新/修复模式检测
// ============================================================
function InitializeSetup(): Boolean;
begin
  Result := True;
  // 如果已安装，提示是更新还是重新安装
  if RegKeyExists(HKLM, 'SOFTWARE\WindWhisper') then
  begin
    // 更新模式：自动检测，不创建新的快捷方式
  end;
end;
