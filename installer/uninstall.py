# -*- coding: utf-8 -*-
"""
风语_卸载.exe — 卸载程序
功能：删除程序文件 → 询问是否删除 config.json → 删除快捷方式 → 清理注册表
"""

import os
import sys
import shutil
import ctypes
from pathlib import Path
import winreg

# ── 常量 ──────────────────────────────────────────────
APP_NAME = "风语"
DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), APP_NAME)
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


def find_install_dir():
    """从注册表读取安装路径"""
    install_dir = None
    # HKLM
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)
        install_dir, _ = winreg.QueryValueEx(key, "InstallLocation")
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # HKCU
    if not install_dir:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
            install_dir, _ = winreg.QueryValueEx(key, "InstallLocation")
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception:
            pass

    # 默认路径
    if not install_dir or not Path(install_dir).exists():
        default_check = Path(DEFAULT_INSTALL_DIR)
        if default_check.exists() and (default_check / "风语.exe").exists():
            install_dir = str(default_check)

    return install_dir


def remove_shortcut():
    """删除桌面快捷方式"""
    try:
        import win32com.client
    except ImportError:
        # fallback: 直接删文件
        pass

    desktop_paths = [
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop",
    ]

    for desktop in desktop_paths:
        shortcut = desktop / f"{APP_NAME}.lnk"
        if shortcut.exists():
            try:
                shortcut.unlink()
                print(f"[OK] 已删除快捷方式: {shortcut}")
            except Exception as e:
                print(f"[警告] 删除快捷方式失败: {e}")


def remove_registry():
    """清理注册表卸载信息"""
    # 尝试 HKLM
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)
        print("[OK] 注册表卸载信息已清理 (HKLM)")
        return
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # 尝试 HKCU
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        print("[OK] 注册表卸载信息已清理 (HKCU)")
    except FileNotFoundError:
        print("[提示] 注册表中未找到卸载信息")
    except Exception as e:
        print(f"[警告] 清理注册表失败: {e}")


def remove_files(install_dir, delete_config):
    """删除安装目录中的文件"""
    install_path = Path(install_dir)

    # 1. 询问是否删除 config.json
    config_file = install_path / "config.json"
    if config_file.exists():
        if delete_config:
            try:
                config_file.unlink()
                print(f"[OK] 已删除 config.json")
            except Exception as e:
                print(f"[警告] 删除 config.json 失败: {e}")
        else:
            print("[OK] config.json 已保留（用户选择保留）")

    # 2. 删除整个安装目录
    if install_path.exists():
        print(f"  正在删除安装目录: {install_path}")
        try:
            # 先删除 exe 文件（可能被占用）
            for exe_name in ["风语.exe", "风语_卸载.exe", "风语_更新.exe"]:
                exe_file = install_path / exe_name
                if exe_file.exists():
                    try:
                        exe_file.unlink()
                    except PermissionError:
                        print(f"[提示] {exe_name} 正在运行或被占用，无法删除")
                        print("       请关闭程序后重新运行卸载。")

            # 删除剩余文件和目录
            shutil.rmtree(str(install_path), ignore_errors=True)
            print("[OK] 安装目录已删除")
        except Exception as e:
            print(f"[警告] 删除安装目录失败: {e}")
            print("       请手动删除:", install_path)


def main():
    if not is_admin():
        print("[提示] 需要管理员权限，正在重新启动...")
        relaunch_as_admin()
        return

    print(f"\n{'='*50}")
    print(f"  {APP_NAME} 卸载程序")
    print(f"{'='*50}")

    # 检测安装目录
    install_dir = find_install_dir()

    if not install_dir:
        print("\n[错误] 未检测到已安装的风语程序。")
        print("注册表中没有卸载信息，可能已卸载或未安装。")
        try:
            user_input = input("\n如果你知道安装路径，可以手动输入 (直接回车退出): ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = ""
        if user_input and Path(user_input).exists():
            install_dir = os.path.abspath(user_input)
        else:
            print("卸载程序退出。")
            input("\n按 Enter 退出...")
            sys.exit(0)
    else:
        print(f"\n检测到安装路径: {install_dir}")

    # 确认卸载
    try:
        confirm = input("\n确认卸载风语？(Y/n) > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        confirm = ""
    if confirm == "n":
        print("卸载已取消。")
        input("\n按 Enter 退出...")
        sys.exit(0)

    # 询问是否删除 config.json
    delete_config = False
    config_file = Path(install_dir) / "config.json"
    if config_file.exists():
        print(f"\n你的配置文件 config.json 位于: {config_file}")
        print("其中包含邮箱授权码、数据路径等个人配置。")
        try:
            ans = input("是否同时删除配置文件？(y/N) > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans == "y":
            delete_config = True

    # 执行卸载
    print(f"\n{'─'*50}")
    print("正在卸载，请稍候...")
    print(f"{'─'*50}")

    remove_shortcut()
    remove_registry()
    remove_files(install_dir, delete_config)

    print(f"\n{'='*50}")
    print(f"  {APP_NAME} 卸载完成！")
    print(f"{'='*50}")

    if not delete_config and config_file.exists():
        print(f"\n配置文件已保留: {config_file}")
        print("如需彻底删除，请手动移除该文件。")

    try:
        input("\n按 Enter 退出...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
