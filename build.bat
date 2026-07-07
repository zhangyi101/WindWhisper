@echo off
echo ========================================
echo   风哨 - 打包工具
echo ========================================
echo.

REM 检查依赖
pip install pyqt5 openpyxl nrgpy pywin32 pyinstaller

REM 打包
pyinstaller --onefile --windowed ^
  --name="风语" ^
  --add-data="resources;resources" ^
  main.py

echo.
echo 打包完成！exe 在 dist\风哨.exe
pause
