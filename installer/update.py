# -*- coding: utf-8 -*-
"""
风语_更新.exe — 更新/修复程序
功能：从注册表检测安装目录 → 覆盖 风语.exe + resources
      → 不碰 config.json → 提示完成
"""

import os
import sys
import shutil
import ctypes
from pathlib import Path
import winreg

# ── 常量 ──────────────────────────────────────────────
APP_NAME = "风语"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "WindWatcher"
DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), APP_NAME)

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = Path(__file__).resolve().parent

UNINSTALL_KEY = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def relaunch_as_admin():
    script = sys.argv[0]
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", script, params, None, 1)
    sys.exit(0)


def get_resource_path(relative_path):
    return BUNDLE_DIR / relative_path


def find_install_dir():
    """从注册表读取安装路径；找不到则提示用户手动输入"""
    # 1. 尝试从注册表 HKLM 读取
    install_dir = None
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)
        install_dir, _ = winreg.QueryValueEx(key, "InstallLocation")
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # 2. 尝试从注册表 HKCU 读取（万一非管理员安装的）
    if not install_dir:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
            install_dir, _ = winreg.QueryValueEx(key, "InstallLocation")
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception:
            pass

    # 3. 检查默认路径是否存在
    if not install_dir or not Path(install_dir).exists():
        default_check = Path(DEFAULT_INSTALL_DIR)
        if default_check.exists() and (default_check / "风语.exe").exists():
            install_dir = str(default_check)

    return install_dir


def update_files(install_dir):
    """覆盖更新 风语.exe 和 resources，不碰 config.json"""
    install_path = Path(install_dir)

    # 1. 覆盖 风语.exe
    exe_src = get_resource_path("风语.exe")
    if not exe_src.exists():
        print(f"[错误] 找不到 风语.exe: {exe_src}")
        sys.exit(1)

    exe_dst = install_path / "风语.exe"
    print(f"  更新 风语.exe ...")
    shutil.copy2(str(exe_src), str(exe_dst))

    # 2. 覆盖 resources 目录
    res_src = get_resource_path("resources")
    if res_src.exists() and res_src.is_dir():
        res_dst = install_path / "resources"
        print(f"  更新 resources/ ...")
        if res_dst.exists():
            shutil.rmtree(str(res_dst))
        shutil.copytree(str(res_src), str(res_dst))

    # 3. config.json — 绝对不碰
    config_file = install_path / "config.json"
    if config_file.exists():
        print(f"  config.json → 保留用户配置，未修改")
    else:
        # 如果 config.json 不存在，从 template 创建一份
        config_src = get_resource_path("config.json.template")
        if config_src.exists():
            print(f"  config.json 不存在，从模板创建 ...")
            shutil.copy2(str(config_src), str(config_file))

    print(f"\n[OK] 更新完成")
    return install_path


def update_registry(install_dir):
    """更新注册表版本号"""
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
        winreg.CloseKey(key)
        print(f"[OK] 注册表版本信息已更新")
    except Exception as e:
        print(f"[警告] 更新注册表失败: {e}")


def main():
    if not is_admin():
        print("[提示] 需要管理员权限，正在重新启动...")
        relaunch_as_admin()
        return

    print(f"\n{'='*50}")
    print(f"  {APP_NAME} 更新/修复程序 v{APP_VERSION}")
    print(f"{'='*50}")

    # 检测安装目录
    install_dir = find_install_dir()

    if not install_dir:
        print("\n[错误] 未检测到已安装的风语程序。")
        print("请先运行「风语_安装.exe」进行首次安装。")
        print(f"\n如果你知道安装路径，可以手动输入:")
        try:
            user_input = input("安装路径> ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = ""
        if user_input and Path(user_input).exists() and (Path(user_input) / "风语.exe").exists():
            install_dir = os.path.abspath(user_input)
        else:
            print("路径无效或未找到 风语.exe，更新中止。")
            input("\n按 Enter 退出...")
            sys.exit(1)
    else:
        print(f"\n检测到安装路径: {install_dir}")

        # 确认路径
        try:
            confirm = input("\n使用此路径进行更新？(Y/n) > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            confirm = ""
        if confirm == "n":
            try:
                user_input = input("请输入安装路径: ").strip()
            except (EOFError, KeyboardInterrupt):
                user_input = ""
            if user_input and Path(user_input).exists():
                install_dir = os.path.abspath(user_input)
            else:
                print("路径无效，更新中止。")
                input("\n按 Enter 退出...")
                sys.exit(1)

    # 执行更新
    print(f"\n{'─'*50}")
    print("正在更新，请稍候...")
    print(f"{'─'*50}")

    update_files(install_dir)
    update_registry(install_dir)

    print(f"\n{'='*50}")
    print(f"  {APP_NAME} 更新完成！")
    print(f"{'='*50}")
    print(f"\n安装目录: {install_dir}")
    print(f"用户配置 (config.json) 已保留。")

    try:
        input("\n按 Enter 退出...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
