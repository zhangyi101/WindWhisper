@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
echo ============================================================
echo   风语 安装包三件套 — 打包脚本
echo ============================================================
echo.

cd /d "%~dp0.."
set PROJECT_ROOT=%CD%
set VENV_PY=%PROJECT_ROOT%\venv\Scripts\python.exe
set OUT=%PROJECT_ROOT%\installer_output

if not exist "%VENV_PY%" (
    echo [错误] 找不到 venv 的 Python: %VENV_PY%
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\dist\风语.exe" (
    echo [错误] 找不到主程序: %PROJECT_ROOT%\dist\风语.exe
    echo        请先打包主程序。
    pause
    exit /b 1
)

if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"
mkdir "%OUT%\_build"

echo [步骤 1/3] 打包 风语_卸载.exe ...
"%VENV_PY%" -m PyInstaller --onefile --windowed --uac-admin ^
  --name "风语_卸载" ^
  --distpath "%OUT%" ^
  --workpath "%OUT%\_build" ^
  --specpath "%OUT%\_build" ^
  --clean --noconfirm ^
  "installer\uninstall.py"
if errorlevel 1 goto :fail
echo   完成。
echo.

echo [步骤 2/3] 打包 风语_更新.exe ...
"%VENV_PY%" -m PyInstaller --onefile --windowed --uac-admin ^
  --name "风语_更新" ^
  --add-data "dist\风语.exe;." ^
  --add-data "resources;resources" ^
  --add-data "config.json.template;." ^
  --add-data "INSTALL.md;." ^
  --add-data "%OUT%\风语_卸载.exe;." ^
  --distpath "%OUT%" ^
  --workpath "%OUT%\_build" ^
  --specpath "%OUT%\_build" ^
  --clean --noconfirm ^
  "installer\update.py"
if errorlevel 1 goto :fail
echo   完成。
echo.

echo [步骤 3/3] 打包 风语_安装.exe ...
"%VENV_PY%" -m PyInstaller --onefile --windowed --uac-admin ^
  --name "风语_安装" ^
  --add-data "dist\风语.exe;." ^
  --add-data "resources;resources" ^
  --add-data "config.json.template;." ^
  --add-data "INSTALL.md;." ^
  --add-data "README.md;." ^
  --add-data "%OUT%\风语_更新.exe;." ^
  --add-data "%OUT%\风语_卸载.exe;." ^
  --distpath "%OUT%" ^
  --workpath "%OUT%\_build" ^
  --specpath "%OUT%\_build" ^
  --clean --noconfirm ^
  "installer\install.py"
if errorlevel 1 goto :fail
echo   完成。
echo.

rmdir /s /q "%OUT%\_build" 2>nul

echo ============================================================
echo   打包完成！输出目录: %OUT%
echo ============================================================
dir /b "%OUT%"
echo.
pause
exit /b 0

:fail
echo.
echo [失败] 打包出错，请查看上方日志。
pause
exit /b 1
