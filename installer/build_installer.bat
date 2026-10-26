@echo off
REM FengYu WindWhisper - build all installers
REM Double-click this file to rebuild: main app + 3 installers + release package
cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found: venv\Scripts\python.exe
    pause
    exit /b 1
)
venv\Scripts\python.exe installer\build_installer.py
if errorlevel 1 (
    echo.
    echo [FAIL] build failed. See log above.
    pause
    exit /b 1
)
venv\Scripts\python.exe installer\assemble_package.py
echo.
echo All done. Output: installer_output\ and release package folder.
pause
