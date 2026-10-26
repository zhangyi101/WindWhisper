# -*- coding: utf-8 -*-
"""
风语_卸载.exe — 卸载程序 (GUI)

功能：
  1. 从注册表检测安装目录
  2. 删除程序文件（保留/删除 config.json 由用户选择）
  3. 删除桌面快捷方式
  4. 清理注册表卸载信息
  5. 不动测风数据目录（D:\\测风数据文件）

命令行：
  风语_卸载.exe             → GUI
  风语_卸载.exe --silent    → 静默卸载（保留配置）
  风语_卸载.exe --silent --purge → 静默卸载并删除配置
"""
import os
import sys
import shutil
import ctypes
import time
from pathlib import Path
import winreg

APP_NAME = "风语"
DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), APP_NAME)
UNINSTALL_KEY = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    script = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    if not getattr(sys, 'frozen', False):
        params = f'"{sys.argv[0]}" {params}'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", script, params, None, 1)
    if ret <= 32:
        ctypes.windll.user32.MessageBoxW(
            0, "需要管理员权限才能卸载。\n请右键 → 以管理员身份运行。",
            f"{APP_NAME} 卸载", 0x10
        )
    sys.exit(0)


def get_desktop_dirs():
    dirs = []
    up = os.environ.get("USERPROFILE")
    if up:
        d = Path(up) / "Desktop"
        if d.exists():
            dirs.append(d)
    public = os.environ.get("PUBLIC", r"C:\Users\Public")
    for name in ("Desktop", "桌面"):
        d = Path(public) / name
        if d.exists() and d not in dirs:
            dirs.append(d)
    return dirs


def remove_shortcuts():
    removed = []
    for desktop in get_desktop_dirs():
        for name in (APP_NAME, f"{APP_NAME}_更新", f"{APP_NAME}_卸载"):
            lnk = desktop / f"{name}.lnk"
            if lnk.exists():
                try:
                    lnk.unlink()
                    removed.append(str(lnk))
                except Exception:
                    pass
    return removed


def find_install_dir():
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, UNINSTALL_KEY)
            d, _ = winreg.QueryValueEx(key, "InstallLocation")
            winreg.CloseKey(key)
            if d and Path(d).exists():
                return d
        except Exception:
            pass
    p = Path(DEFAULT_INSTALL_DIR)
    if (p / "风语.exe").exists():
        return str(p)
    for candidate in [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / APP_NAME,
        Path("D:/" + APP_NAME),
        Path("D:/Program Files/" + APP_NAME),
    ]:
        if candidate.exists() and (candidate / "风语.exe").exists():
            return str(candidate)
    return None


def remove_registry():
    removed = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            winreg.DeleteKey(hive, UNINSTALL_KEY)
            removed.append(hive == winreg.HKEY_LOCAL_MACHINE and "HKLM" or "HKCU")
        except FileNotFoundError:
            pass
        except Exception:
            pass
    return removed


def do_uninstall(install_dir, delete_config=False, progress_cb=None):
    """执行卸载。返回 (success, msgs)"""
    msgs = []

    def log(s):
        msgs.append(s)
        if progress_cb:
            progress_cb(s)

    ip = Path(install_dir)

    # 1. 删除桌面快捷方式
    log("删除桌面快捷方式 ...")
    removed = remove_shortcuts()
    if removed:
        for r in removed:
            log(f"  已删除 {r}")
    else:
        log("  无快捷方式需删除")

    # 2. 清理注册表
    log("清理注册表 ...")
    regs = remove_registry()
    log(f"  已清理: {', '.join(regs)}" if regs else "  无注册表项")

    # 3. 删除文件
    if ip.exists():
        log(f"删除安装目录: {ip}")

        # 先尝试删除 exe（可能被占用）
        for exe in ("风语.exe", "风语_更新.exe", "风语_卸载.exe"):
            f = ip / exe
            if f.exists():
                for attempt in range(5):
                    try:
                        f.unlink()
                        break
                    except PermissionError:
                        if attempt < 4:
                            time.sleep(0.5)
                        else:
                            log(f"  [警告] {exe} 被占用，无法删除")

        # config.json：保留时备份到用户目录，删除时直接删
        cfg = ip / "config.json"
        if cfg.exists():
            if delete_config:
                try:
                    cfg.unlink()
                    log("  已删除 config.json")
                except Exception as e:
                    log(f"  [警告] 删除 config.json 失败: {e}")
            else:
                backup_dir = Path(os.environ.get(
                    "LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")
                )) / APP_NAME
                try:
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup_file = backup_dir / "config.json.bak"
                    shutil.copy2(str(cfg), str(backup_file))
                    log(f"  config.json 已备份到: {backup_file}")
                except Exception as e:
                    # 备份失败就退回到复制到桌面
                    try:
                        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
                        fallback = desktop / "风语_config备份.json"
                        shutil.copy2(str(cfg), str(fallback))
                        log(f"  config.json 已备份到桌面: {fallback}")
                    except Exception:
                        log(f"  [警告] 配置备份失败: {e}")

        # 剩余目录
        try:
            shutil.rmtree(str(ip), ignore_errors=True)
        except Exception:
            pass
        # 目录可能因句柄延迟残留，重试 rmdir
        if ip.exists():
            for _ in range(6):
                try:
                    remaining = list(ip.iterdir()) if ip.is_dir() else None
                except Exception:
                    remaining = None
                if remaining == []:
                    try:
                        ip.rmdir()
                        break
                    except Exception:
                        time.sleep(0.4)
                else:
                    break
        if not ip.exists():
            log("  安装目录已删除")
        else:
            try:
                empty = list(ip.iterdir()) == []
            except Exception:
                empty = False
            if empty:
                log("  安装目录已清空（目录本身残留，重启后自动消失）")
            else:
                log(f"  [提示] 目录未完全删除，可能有文件被占用: {ip}")
    else:
        log("安装目录不存在，跳过文件删除")

    # 4. 清理配置备份目录（purge 时一并删）
    backup_dir = Path(os.environ.get(
        "LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")
    )) / APP_NAME
    if backup_dir.exists():
        if delete_config:
            try:
                shutil.rmtree(str(backup_dir), ignore_errors=True)
                log(f"  配置备份目录已删除: {backup_dir}")
            except Exception as e:
                log(f"  [警告] 删除备份目录失败: {e}")
        else:
            log(f"  配置备份保留: {backup_dir}")

    return True, msgs


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title(f"{APP_NAME} 卸载程序")
    root.geometry("640x620")
    root.minsize(620, 580)
    root.resizable(False, True)

    # 顶部标题
    header = tk.Frame(root)
    header.pack(side="top", fill="x", pady=(16, 0))
    tk.Label(header, text=f"{APP_NAME} 卸载", font=("Microsoft YaHei", 16, "bold")).pack()
    tk.Label(header, text="删除程序文件、桌面快捷方式与注册表项",
             font=("Microsoft YaHei", 9), fg="#666").pack(pady=(2, 0))

    # 底部按钮区（先占位，避免被内容挤掉）
    btn_frame = tk.Frame(root)
    btn_frame.pack(side="bottom", fill="x", pady=14)

    # 中间内容
    frame = tk.Frame(root, padx=20, pady=8)
    frame.pack(side="top", fill="both", expand=True)

    detected = find_install_dir()
    path_row = tk.Frame(frame)
    path_row.pack(fill="x", pady=(6, 4))
    tk.Label(path_row, text="安装目录：", font=("Microsoft YaHei", 10)).pack(side="left")
    path_var = tk.StringVar(value=detected or "")
    tk.Entry(path_row, textvariable=path_var, width=42,
             font=("Consolas", 9)).pack(side="left", fill="x", expand=True, padx=(0, 6))

    def browse():
        d = filedialog.askdirectory(title="选择风语安装目录", initialdir=path_var.get() or "C:/")
        if d:
            path_var.set(os.path.normpath(d))

    tk.Button(path_row, text="浏览...", command=browse, width=7).pack(side="left")

    status = f"检测到安装：{detected}" if detected else "未在注册表中检测到风语安装。"
    tk.Label(frame, text=status, justify="left", anchor="w", font=("Microsoft YaHei", 9),
             fg="#2e7d32" if detected else "#c62828").pack(fill="x", pady=(4, 8))

    # 保留配置选项
    keep_var = tk.BooleanVar(value=True)
    tk.Checkbutton(frame, text="保留 config.json（邮箱授权码、路径配置）\n"
                              "保留时会备份到用户目录，重装自动恢复",
                   variable=keep_var, font=("Microsoft YaHei", 9),
                   justify="left").pack(anchor="w", pady=(2, 6))

    tip = ("不删除：测风数据目录（D:\\测风数据文件）以及 SymphoniePRO Desktop 等第三方软件")
    tk.Label(frame, text=tip, justify="left", anchor="w",
             font=("Microsoft YaHei", 8), fg="#888").pack(fill="x", pady=(0, 8))

    tk.Label(frame, text="卸载进度：", font=("Microsoft YaHei", 9),
             anchor="w").pack(fill="x")
    log_box = tk.Text(frame, height=7, font=("Consolas", 8), state="disabled",
                      bg="#f7f7f7", relief="solid", borderwidth=1, wrap="word")
    log_box.pack(fill="both", expand=True, pady=(2, 6))

    def append_log(t):
        log_box.config(state="normal")
        log_box.insert("end", t + "\n")
        log_box.see("end")
        log_box.config(state="disabled")
        root.update_idletasks()

    def start_uninstall():
        target = path_var.get().strip()
        if not target:
            messagebox.showwarning("提示", "未检测到安装目录。\n如已安装请手动选择。")
            return
        target = os.path.abspath(os.path.expandvars(target))

        if not messagebox.askyesno("确认卸载",
                                   f"确定卸载 {APP_NAME}？\n\n目录：{target}\n"
                                   f"配置：{'保留' if keep_var.get() else '一并删除'}"):
            return

        un_btn.config(state="disabled")
        append_log(f"开始卸载: {target}")
        ok, msgs = do_uninstall(target, delete_config=not keep_var.get(), progress_cb=append_log)
        if ok:
            append_log("─" * 40)
            append_log("卸载完成！")
            messagebox.showinfo("卸载完成", f"{APP_NAME} 已卸载。")
            root.destroy()
        else:
            messagebox.showerror("卸载失败", "\n".join(msgs[-3:]))
            un_btn.config(state="normal")

    inner_btn = tk.Frame(btn_frame)
    inner_btn.pack()
    un_btn = tk.Button(inner_btn, text="确认卸载", command=start_uninstall,
                       width=16, height=2, bg="#c62828", fg="white",
                       font=("Microsoft YaHei", 10, "bold"))
    un_btn.pack(side="left", padx=8)
    tk.Button(inner_btn, text="取消", command=root.destroy, width=10, height=2,
              font=("Microsoft YaHei", 10)).pack(side="left", padx=8)

    root.mainloop()


def run_silent(target=None, purge=False):
    if not target:
        target = find_install_dir()
    logs = []
    if not target:
        logs.append("RESULT=FAIL: 未检测到已安装的风语")
        try:
            (Path(os.environ.get("TEMP", ".")) / "fengyu_uninstall.log").write_text(
                "\n".join(logs), encoding="utf-8")
        except Exception:
            pass
        return 1
    logs.append(f"卸载目录: {target}  删除配置={purge}")

    def cb(s):
        logs.append(s)
        try:
            print("  " + s)
        except Exception:
            pass

    ok, msgs = do_uninstall(target, delete_config=purge, progress_cb=cb)
    logs.append(f"RESULT={'OK' if ok else 'FAIL'}")
    try:
        (Path(os.environ.get("TEMP", ".")) / "fengyu_uninstall.log").write_text(
            "\n".join(logs), encoding="utf-8")
    except Exception:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    silent = "--silent" in args
    purge = "--purge" in args
    target = None
    if "--dir" in args:
        i = args.index("--dir")
        if i + 1 < len(args):
            target = args[i + 1]

    if not is_admin():
        print("[提示] 非管理员模式：将尝试清理 HKCU 注册表")

    if silent:
        sys.exit(run_silent(target, purge))
    else:
        run_gui()
