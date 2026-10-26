# -*- coding: utf-8 -*-
"""
风语 安装包三件套 — 打包脚本（Python 版，比 .bat 可靠）

顺序很重要：
  1. 卸载 exe（无依赖）
  2. 更新 exe（内嵌 主程序 + resources + 卸载 exe）
  3. 安装 exe（内嵌 主程序 + resources + 更新 exe + 卸载 exe）
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"
OUT = ROOT / "installer_output"
BUILD = OUT / "_build"
DIST_EXE = ROOT / "dist" / "风语.exe"


def run(cmd, desc):
    print(f"\n{'='*60}\n{desc}\n{'='*60}")
    r = subprocess.run(cmd, cwd=str(ROOT))
    if r.returncode != 0:
        print(f"[FAIL] {desc} 失败 (exit {r.returncode})")
        return False
    print(f"[OK] {desc}")
    return True


def main():
    if not VENV_PY.exists():
        print(f"[ERROR] 找不到 venv Python: {VENV_PY}")
        return 1
    if not DIST_EXE.exists():
        print(f"[ERROR] 找不到主程序: {DIST_EXE}")
        return 1

    if OUT.exists():
        shutil.rmtree(str(OUT), ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    base = [str(VENV_PY), "-m", "PyInstaller", "--onefile", "--windowed",
            "--clean", "--noconfirm",
            "--distpath", str(OUT), "--workpath", str(BUILD), "--specpath", str(BUILD)]

    # ---- 1. 卸载 ----
    if not run(base + ["--name", "风语_卸载", str(ROOT / "installer" / "uninstall.py")],
               "打包 风语_卸载.exe"):
        return 1

    uninstaller = OUT / "风语_卸载.exe"
    if not uninstaller.exists():
        print("[ERROR] 风语_卸载.exe 未生成")
        return 1

    # ---- 2. 更新 ----
    if not run(base + [
        "--name", "风语_更新",
        "--add-data", f"{DIST_EXE};.",
        "--add-data", f"{ROOT / 'resources'};resources",
        "--add-data", f"{ROOT / 'config.json.template'};.",
        "--add-data", f"{ROOT / 'INSTALL.md'};.",
        "--add-data", f"{uninstaller};.",
        str(ROOT / "installer" / "update.py"),
    ], "打包 风语_更新.exe"):
        return 1

    updater = OUT / "风语_更新.exe"
    if not updater.exists():
        print("[ERROR] 风语_更新.exe 未生成")
        return 1

    # ---- 3. 安装 ----
    # 不再内嵌更新/卸载 exe：安装程序会从自身所在目录（安装包文件夹）复制它们
    if not run(base + [
        "--name", "风语_安装",
        "--add-data", f"{DIST_EXE};.",
        "--add-data", f"{ROOT / 'resources'};resources",
        "--add-data", f"{ROOT / 'config.json.template'};.",
        "--add-data", f"{ROOT / 'INSTALL.md'};.",
        "--add-data", f"{ROOT / 'README.md'};.",
        str(ROOT / "installer" / "install.py"),
    ], "打包 风语_安装.exe"):
        return 1

    # 清理中间产物
    shutil.rmtree(str(BUILD), ignore_errors=True)

    print(f"\n{'='*60}\n打包完成\n{'='*60}")
    for f in sorted(OUT.glob("*.exe")):
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {f.name:24s} {size_mb:7.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
