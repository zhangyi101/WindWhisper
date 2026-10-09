@echo off
chcp 65001 >nul
echo ============================================
echo   风语 / WindWhisper v2.0 环境安装
echo ============================================
echo.

echo [1/4] 检查 Python...
python --version 2>nul
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3.8+
    echo    下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [2/4] 创建虚拟环境...
if not exist venv (
    python -m venv venv
    echo ✅ 虚拟环境已创建
) else (
    echo ℹ 虚拟环境已存在，跳过
)

echo.
echo [3/4] 安装依赖...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 依赖安装失败，请检查网络或手动安装
    pause
    exit /b 1
)

echo.
echo [4/4] 检查 SymphoniePRO Desktop...
if exist "C:\Program Files (x86)\Renewable NRG Systems\SymPRO Desktop\SymPRODesktop.exe" (
    echo ✅ SymphoniePRO Desktop 已安装
) else (
    echo ⚠ 未找到 SymphoniePRO Desktop
    echo    如需解密 .rld 文件，请从 NRG Systems 官网下载安装
    echo    https://www.renewablenrgsystems.com/
)

echo.
echo ============================================
echo   安装完成！
echo   运行方式: venv\Scripts\activate ^&^& python main.py
echo   或双击 config.json 配置后直接运行
echo ============================================
pause
