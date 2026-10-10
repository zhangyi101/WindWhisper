@echo off
chcp 65001 >nul 2>&1
REM ===================================================================
REM  风语安装包打包脚本 — 一次性打包 3 个 exe
REM  输出目录: D:\WindWatcher\installer_output\
REM ===================================================================

setlocal enabledelayedexpansion

set PROJECT_DIR=D:\WindWatcher
set INSTALLER_DIR=%PROJECT_DIR%\installer
set OUTPUT_DIR=%PROJECT_DIR%\installer_output
set VENV_PY=%PROJECT_DIR%\venv\Scripts\python.exe
set DIST_DIR=%PROJECT_DIR%\dist

echo ================================================================
echo   风语安装包打包脚本
echo   项目目录: %PROJECT_DIR%
echo   输出目录: %OUTPUT_DIR%
echo ================================================================
echo.

REM ── 前置检查 ──────────────────────────────────────────
if not exist "%VENV_PY%" (
    echo [错误] 找不到 venv Python: %VENV_PY%
    echo 请确认 venv 已创建。
    pause
    exit /b 1
)

if not exist "%DIST_DIR%\风语.exe" (
    echo [错误] 找不到 %DIST_DIR%\风语.exe
    echo 请先运行主程序打包（build.bat）。
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%\resources" (
    echo [错误] 找不到 %PROJECT_DIR%\resources
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%\config.json.template" (
    echo [错误] 找不到 %PROJECT_DIR%\config.json.template
    pause
    exit /b 1
)

echo [OK] 前置检查通过
echo.

REM ── 创建输出目录 ──────────────────────────────────────
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM ── 清理旧的 build/spec ───────────────────────────────
if exist "%INSTALLER_DIR\build" rmdir /s /q "%INSTALLER_DIR\build"
if exist "%INSTALLER_DIR\__pycache__" rmdir /s /q "%INSTALLER_DIR\__pycache__"

REM ================================================================
REM  1/3  打包 风语_安装.exe
REM ================================================================
echo ────────────────────────────────────────────────────────────────
echo  [1/3] 打包 风语_安装.exe ...
echo ────────────────────────────────────────────────────────────────

"%VENV_PY%" -m PyInstaller ^
    --onefile ^
    --uac-admin ^
    --name "风语_安装" ^
    --distpath "%OUTPUT_DIR%" ^
    --workpath "%INSTALLER_DIR%\build" ^
    --specpath "%INSTALLER_DIR%" ^
    --add-data "%DIST_DIR%\风语.exe;." ^
    --add-data "%PROJECT_DIR%\resources;resources" ^
    --add-data "%PROJECT_DIR%\config.json.template;." ^
    "%INSTALLER_DIR%\install.py"

if errorlevel 1 (
    echo [失败] 风语_安装.exe 打包失败！
    pause
    exit /b 1
)

echo [OK] 风语_安装.exe 打包成功
echo.

REM ================================================================
REM  2/3  打包 风语_更新.exe
REM ================================================================
echo ────────────────────────────────────────────────────────────────
echo  [2/3] 打包 风语_更新.exe ...
echo ────────────────────────────────────────────────────────────────

"%VENV_PY%" -m PyInstaller ^
    --onefile ^
    --uac-admin ^
    --name "风语_更新" ^
    --distpath "%OUTPUT_DIR%" ^
    --workpath "%INSTALLER_DIR%\build" ^
    --specpath "%INSTALLER_DIR%" ^
    --add-data "%DIST_DIR%\风语.exe;." ^
    --add-data "%PROJECT_DIR%\resources;resources" ^
    --add-data "%PROJECT_DIR%\config.json.template;." ^
    "%INSTALLER_DIR%\update.py"

if errorlevel 1 (
    echo [失败] 风语_更新.exe 打包失败！
    pause
    exit /b 1
)

echo [OK] 风语_更新.exe 打包成功
echo.

REM ================================================================
REM  3/3  打包 风语_卸载.exe
REM ================================================================
echo ────────────────────────────────────────────────────────────────
echo  [3/3] 打包 风语_卸载.exe ...
echo ────────────────────────────────────────────────────────────────

"%VENV_PY%" -m PyInstaller ^
    --onefile ^
    --uac-admin ^
    --name "风语_卸载" ^
    --distpath "%OUTPUT_DIR%" ^
    --workpath "%INSTALLER_DIR%\build" ^
    --specpath "%INSTALLER_DIR%" ^
    "%INSTALLER_DIR%\uninstall.py"

if errorlevel 1 (
    echo [失败] 风语_卸载.exe 打包失败！
    pause
    exit /b 1
)

echo [OK] 风语_卸载.exe 打包成功
echo.

REM ── 清理中间文件 ─────────────────────────────────────
if exist "%INSTALLER_DIR%\build" rmdir /s /q "%INSTALLER_DIR%\build"
if exist "%INSTALLER_DIR%\__pycache__" rmdir /s /q "%INSTALLER_DIR%\__pycache__"
del /q "%INSTALLER_DIR%\风语_安装.spec" 2>nul
del /q "%INSTALLER_DIR%\风语_更新.spec" 2>nul
del /q "%INSTALLER_DIR%\风语_卸载.spec" 2>nul

REM ================================================================
REM  打包完成 — 验证输出
REM ================================================================
echo ================================================================
echo   打包完成！输出目录: %OUTPUT_DIR%
echo ================================================================
echo.

dir "%OUTPUT_DIR%\*.exe"

echo.
echo ================================================================
echo   三个安装包 exe 生成完毕
echo ================================================================
echo.
pause
