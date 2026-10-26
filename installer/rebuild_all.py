# -*- coding: utf-8 -*-
"""一键重建：主程序 → 三件套 → 安装包"""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"


def run(cmd, desc):
    print(f"\n{'='*60}\n{desc}\n{'='*60}", flush=True)
    r = subprocess.run(cmd, cwd=str(ROOT))
    if r.returncode != 0:
        print(f"[FAIL] {desc}")
        sys.exit(1)
    print(f"[OK] {desc}", flush=True)


def kill_running():
    """杀掉正在运行的旧版本，否则 dist 会被占用无法覆盖"""
    import time
    names = ["风语", "风语_安装", "风语_更新", "风语_卸载"]
    for n in names:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-Process -Name '{n}' -ErrorAction SilentlyContinue | Stop-Process -Force"],
            capture_output=True)
    time.sleep(2)


def main():
    kill_running()
    # 1. 主程序
    for p in (ROOT / "build", ROOT / "风语.spec"):
        if p.is_dir():
            shutil.rmtree(str(p), ignore_errors=True)
        elif p.exists():
            p.unlink()
    run([str(VENV_PY), "-m", "PyInstaller", "--onefile", "--windowed",
         "--name", "风语", "--add-data", "resources;resources",
         "--hidden-import", "nrgpy", "--clean", "--noconfirm", "main.py"],
        "打包主程序 风语.exe")

    # 2. 三件套
    run([str(VENV_PY), str(ROOT / "installer" / "build_installer.py")], "打包安装程序三件套")

    # 3. 安装包文件夹
    run([str(VENV_PY), str(ROOT / "installer" / "assemble_package.py")], "组装安装包")

    print("\n全部完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
