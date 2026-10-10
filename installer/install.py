# -*- coding: utf-8 -*-
"""
风语_安装.exe — 首次安装程序
功能：选择安装目录 → 复制 风语.exe + resources + config.json.template
      → 创建桌面快捷方式 → 写入注册表卸载信息
"""

import os
import sys
import shutil
import ctypes
import winreg
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────
APP_NAME = "风语"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "WindWatcher"
DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), APP_NAME)

# PyInstaller 内嵌资源路径（打包后 _MEIPASS；开发时脚本所在目录）
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = Path(__file__).resolve().parent

# 安装时从父目录取文件（开发模式）；打包后从 _MEIPASS 取
DIST_DIR = BUNDLE_DIR
RESOURCES_SRC = BUNDLE_DIR / "resources"
CONFIG_TEMPLATE = BUNDLE_DIR / "config.json.template"
APP_EXE_SRC = DIST_DIR / "风语.exe"

# 注册表卸载信息路径
UNINSTALL_KEY = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"


def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def relaunch_as_admin():
    """以管理员权限重新启动自身"""
    script = sys.argv[0]
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", script, params, None, 1)
    sys.exit(0)


def get_resource_path(relative_path):
    """获取内嵌资源路径"""
    return BUNDLE_DIR / relative_path


def choose_install_dir():
    """让用户选择安装目录"""
    print(f"\n{'='*50}")
    print(f"  {APP_NAME} 安装程序 v{APP_VERSION}")
    print(f"{'='*50}")
    print(f"\n默认安装路径: {DEFAULT_INSTALL_DIR}")
    print(f"\n按 Enter 使用默认路径，或输入自定义路径:")

    try:
        user_input = input("安装路径> ").strip()
    except (EOFError, KeyboardInterrupt):
        user_input = ""

    install_dir = user_input if user_input else DEFAULT_INSTALL_DIR

    # 展开环境变量
    install_dir = os.path.expandvars(install_dir)
    install_dir = os.path.abspath(install_dir)

    print(f"\n安装路径: {install_dir}")
    return install_dir


def copy_files(install_dir):
    """复制程序文件到安装目录"""
    install_path = Path(install_dir)
    install_path.mkdir(parents=True, exist_ok=True)

    # 1. 复制 风语.exe
    exe_src = get_resource_path("风语.exe")
    if not exe_src.exists():
        print(f"[错误] 找不到 风语.exe: {exe_src}")
        sys.exit(1)

    exe_dst = install_path / "风语.exe"
    print(f"  复制 风语.exe ...")
    shutil.copy2(str(exe_src), str(exe_dst))

    # 2. 复制 resources 目录
    res_src = get_resource_path("resources")
    if res_src.exists() and res_src.is_dir():
        res_dst = install_path / "resources"
        print(f"  复制 resources/ ...")
        if res_dst.exists():
            shutil.rmtree(str(res_dst))
        shutil.copytree(str(res_src), str(res_dst))

    # 3. 复制 config.json.template → config.json（仅当不存在时）
    config_src = get_resource_path("config.json.template")
    config_dst = install_path / "config.json"
    if config_src.exists():
        if not config_dst.exists():
            print(f"  复制 config.json.template → config.json ...")
            shutil.copy2(str(config_src), str(config_dst))
        else:
            print(f"  config.json 已存在，跳过（保留用户配置）")

    print(f"\n[OK] 文件复制完成")
    return install_path


def create_shortcut(install_path):
    """创建桌面快捷方式"""
    try:
        import win32com.client
    except ImportError:
        print("[警告] pywin32 未安装，跳过快捷方式创建")
        return

    desktop = Path(os.environ.get("USERPROFILE", r"C:\Users\Public")) / "Desktop"
    if not desktop.exists():
        desktop = Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"

    shortcut_path = desktop / f"{APP_NAME}.lnk"
    target = install_path / "风语.exe"
    icon = str(target)

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.TargetPath = str(target)
        shortcut.WorkingDirectory = str(install_path)
        shortcut.IconLocation = icon
        shortcut.Description = f"{APP_NAME} - 测风数据管理工具"
        shortcut.Save()
        print(f"[OK] 桌面快捷方式: {shortcut_path}")
    except Exception as e:
        print(f"[警告] 创建快捷方式失败: {e}")


def write_registry(install_dir):
    """写入注册表卸载信息"""
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)

        install_path = Path(install_dir)
        exe_path = str(install_path / "风语.exe")
        uninstall_exe = str(install_path / "风语_卸载.exe")

        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe_path)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}"')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        print(f"[OK] 注册表卸载信息已写入")
    except Exception as e:
        print(f"[警告] 写入注册表失败: {e}")


def copy_uninstaller(install_dir):
    """将卸载程序复制到安装目录（供控制面板调用）"""
    uninstaller_src = get_resource_path("风语_卸载.exe")
    if not uninstaller_src.exists():
        # 开发模式下卸载器可能还没打包，跳过
        print("[提示] 卸载程序尚未打包，跳过复制")
        return
    uninstaller_dst = Path(install_dir) / "风语_卸载.exe"
    shutil.copy2(str(uninstaller_src), str(uninstaller_dst))
    print(f"[OK] 卸载程序已复制到安装目录")


def main():
    # 检查管理员权限
    if not is_admin():
        print("[提示] 需要管理员权限，正在重新启动...")
        relaunch_as_admin()
        return

    # 选择安装目录
    install_dir = choose_install_dir()

    # 确认安装
    print(f"\n即将安装到: {install_dir}")
    try:
        confirm = input("\n确认安装？(Y/n) > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        confirm = ""
    if confirm == "n":
        print("安装已取消。")
        input("按 Enter 退出...")
        sys.exit(0)

    # 执行安装
    print(f"\n{'─'*50}")
    print("正在安装，请稍候...")
    print(f"{'─'*50}")

    install_path = copy_files(install_dir)
    copy_uninstaller(install_dir)
    create_shortcut(install_path)
    write_registry(install_dir)

    print(f"\n{'='*50}")
    print(f"  {APP_NAME} 安装完成！")
    print(f"{'='*50}")
    print(f"\n安装目录: {install_path}")
    print(f"启动程序: 桌面快捷方式「{APP_NAME}」")
    print(f"卸载方式: 控制面板 → 程序和功能 → {APP_NAME}")

    try:
        input("\n按 Enter 退出...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
