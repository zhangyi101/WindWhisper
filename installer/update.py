# -*- coding: utf-8 -*-
"""
风语_更新.exe — 更新 / 修复程序 (GUI)

功能：
  1. 从注册表检测安装目录（找不到则让用户选）
  2. 覆盖 风语.exe + resources + 更新/卸载程序
  3. 绝对不碰 config.json（保留用户邮箱授权码等配置）
  4. 重建桌面快捷方式「风语」
  5. 更新注册表版本号

命令行：
  风语_更新.exe             → GUI
  风语_更新.exe --silent    → 静默更新
"""
import os
import sys
import shutil
import ctypes
import subprocess
import tempfile
from pathlib import Path
import winreg

APP_NAME = "风语"
APP_VERSION = "2.1.0"
DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), APP_NAME)
UNINSTALL_KEY = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = Path(__file__).resolve().parent


def _find_file(name):
    """先查内嵌，再查 exe 同目录，再查开发目录"""
    p = BUNDLE_DIR / name
    if p.exists():
        return p
    if getattr(sys, 'frozen', False):
        p2 = Path(sys.executable).resolve().parent / name
        if p2.exists():
            return p2
    p3 = Path(__file__).resolve().parent.parent / name
    if p3.exists():
        return p3
    return None


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
            0, "需要管理员权限才能更新。\n请右键 → 以管理员身份运行。",
            f"{APP_NAME} 更新", 0x10
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


def create_shortcut(install_path, shortcut_name=APP_NAME):
    target = install_path / "风语.exe"
    if not target.exists():
        return False, f"目标程序不存在: {target}"
    desktops = get_desktop_dirs()
    if not desktops:
        return False, "找不到桌面目录"

    created, errors = [], []
    for desktop in desktops:
        lnk = desktop / f"{shortcut_name}.lnk"
        ps = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{lnk}")
$Shortcut.TargetPath = "{target}"
$Shortcut.WorkingDirectory = "{install_path}"
$Shortcut.IconLocation = "{target},0"
$Shortcut.Description = "{APP_NAME} - 测风数据管理工具"
$Shortcut.Save()
'''
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1",
                                             delete=False, encoding="utf-8-sig") as f:
                f.write(ps)
                ps_path = f.name
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                "-File", ps_path], capture_output=True, text=True, timeout=30)
            os.unlink(ps_path)
            if lnk.exists():
                created.append(str(lnk))
            else:
                errors.append(f"{lnk}: {r.stderr.strip()[:80]}")
        except Exception as e:
            errors.append(f"{desktop}: {e}")

    return (True, "已更新: " + "; ".join(created)) if created else (False, "; ".join(errors))


def find_install_dir():
    """注册表 → 默认路径 → 常见位置"""
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, UNINSTALL_KEY)
            d, _ = winreg.QueryValueEx(key, "InstallLocation")
            winreg.CloseKey(key)
            if d and (Path(d) / "风语.exe").exists():
                return d
        except Exception:
            pass

    # 默认路径
    p = Path(DEFAULT_INSTALL_DIR)
    if (p / "风语.exe").exists():
        return str(p)

    # 常见自定义位置
    for candidate in [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / APP_NAME,
        Path("D:/" + APP_NAME),
        Path("D:/Program Files/" + APP_NAME),
    ]:
        if candidate.exists() and (candidate / "风语.exe").exists():
            return str(candidate)
    return None


def write_registry(install_dir):
    """更新注册表信息，HKLM 失败降级 HKCU"""
    ip = Path(install_dir)
    exe = str(ip / "风语.exe")

    def _write(hive, name):
        key = winreg.CreateKey(hive, UNINSTALL_KEY)
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(ip))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                          f'"{ip / "风语_卸载.exe"}"')
        winreg.SetValueEx(key, "ModifyPath", 0, winreg.REG_SZ,
                          f'"{ip / "风语_更新.exe"}"')
        winreg.CloseKey(key)
        return name

    try:
        return True, f"注册表已更新（{_write(winreg.HKEY_LOCAL_MACHINE, 'HKLM')}）", "HKLM"
    except Exception:
        pass
    try:
        return True, f"注册表已更新（{_write(winreg.HKEY_CURRENT_USER, 'HKCU')}）", "HKCU"
    except Exception as e:
        return False, f"注册表更新失败: {e}", None


def do_update(install_dir, progress_cb=None):
    """执行更新，返回 (success, msgs)"""
    msgs = []

    def log(s):
        msgs.append(s)
        if progress_cb:
            progress_cb(s)

    ip = Path(install_dir)
    if not ip.exists():
        return False, [f"安装目录不存在: {ip}"]

    # 检查主程序是否在运行
    exe_path = ip / "风语.exe"
    if exe_path.exists():
        try:
            with open(exe_path, "r+b"):
                pass
        except PermissionError:
            return False, ["风语.exe 正在运行，请先关闭程序再更新。"]

    # 1. 覆盖主程序
    src = BUNDLE_DIR / "风语.exe"
    if not src.exists():
        return False, [f"更新包损坏：找不到 风语.exe（{src}）"]
    log("更新 风语.exe ...")
    try:
        shutil.copy2(str(src), str(exe_path))
    except Exception as e:
        return False, msgs + [f"覆盖主程序失败: {e}"]

    # 2. 覆盖 resources
    res_src = BUNDLE_DIR / "resources"
    if res_src.exists():
        log("更新 resources/ ...")
        res_dst = ip / "resources"
        try:
            if res_dst.exists():
                shutil.rmtree(str(res_dst), ignore_errors=True)
            shutil.copytree(str(res_src), str(res_dst))
        except Exception as e:
            log(f"资源更新警告: {e}")

    # 3. 更新/卸载程序自身
    for sub in ("风语_更新.exe", "风语_卸载.exe"):
        s = _find_file(sub)
        if s:
            log(f"更新 {sub} ...")
            try:
                shutil.copy2(str(s), str(ip / sub))
            except Exception:
                pass

    # 4. config.json——绝对不碰
    cfg = ip / "config.json"
    if cfg.exists():
        log("config.json → 保留用户配置，未修改")
    else:
        tpl = BUNDLE_DIR / "config.json.template"
        if tpl.exists():
            log("config.json 不存在，从模板创建")
            shutil.copy2(str(tpl), str(cfg))

    # 5. 桌面快捷方式
    log("更新桌面快捷方式 ...")
    ok, msg = create_shortcut(ip)
    log(msg if ok else f"快捷方式警告: {msg}")

    # 6. 注册表
    ok2, msg2, _hive = write_registry(install_dir)
    log(msg2)

    return True, msgs


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.title(f"{APP_NAME} 更新 / 修复 v{APP_VERSION}")
    root.geometry("560x400")
    root.resizable(False, False)

    tk.Label(root, text=f"{APP_NAME} 更新 / 修复", font=("Microsoft YaHei", 16, "bold")).pack(pady=(18, 2))
    tk.Label(root, text="保留 config.json 用户配置，仅更新程序文件",
             font=("Microsoft YaHei", 9), fg="#666").pack()

    frame = tk.Frame(root, padx=24, pady=16)
    frame.pack(fill="both", expand=True)

    detected = find_install_dir()
    tk.Label(frame, text="安装目录：", font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", pady=6)
    path_var = tk.StringVar(value=detected or DEFAULT_INSTALL_DIR)
    tk.Entry(frame, textvariable=path_var, width=44, font=("Consolas", 9)).grid(row=0, column=1, sticky="w")

    def browse():
        d = filedialog.askdirectory(title="选择风语安装目录", initialdir=path_var.get())
        if d:
            path_var.set(os.path.normpath(d))

    tk.Button(frame, text="浏览...", command=browse, width=8).grid(row=0, column=2, padx=6)

    status = "已检测到已安装的风语程序。" if detected else \
             "未检测到已安装的风语。\n如已安装请手动选择目录，或先运行「风语_安装」。"
    tk.Label(frame, text=status, justify="left", anchor="w",
             font=("Microsoft YaHei", 9),
             fg="#2e7d32" if detected else "#c62828").grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(6, 8))

    log_box = tk.Text(frame, height=8, width=62, font=("Consolas", 8), state="disabled",
                      bg="#f5f5f5", relief="solid", borderwidth=1)
    log_box.grid(row=2, column=0, columnspan=3, pady=6)

    def append_log(t):
        log_box.config(state="normal")
        log_box.insert("end", t + "\n")
        log_box.see("end")
        log_box.config(state="disabled")
        root.update_idletasks()

    btn_frame = tk.Frame(root, pady=12)
    btn_frame.pack()

    def start_update():
        target = path_var.get().strip()
        if not target:
            messagebox.showwarning("提示", "请填写安装目录")
            return
        target = os.path.abspath(os.path.expandvars(target))
        if not (Path(target) / "风语.exe").exists():
            messagebox.showerror("错误", f"该目录下没有 风语.exe：\n{target}\n\n请确认是否正确安装。")
            return

        upd_btn.config(state="disabled")
        append_log(f"更新目录: {target}")
        ok, msgs = do_update(target, append_log)
        if ok:
            append_log("─" * 40)
            append_log("更新完成！")
            messagebox.showinfo("更新完成",
                                f"{APP_NAME} 已更新到 v{APP_VERSION}\n\n"
                                f"目录: {target}\n用户配置已保留。")
            root.destroy()
        else:
            append_log("更新失败")
            messagebox.showerror("更新失败", "\n".join(msgs[-3:]))
            upd_btn.config(state="normal")

    upd_btn = tk.Button(btn_frame, text="开始更新", command=start_update,
                        width=16, height=2, bg="#1565c0", fg="white",
                        font=("Microsoft YaHei", 10, "bold"))
    upd_btn.pack(side="left", padx=8)
    tk.Button(btn_frame, text="取消", command=root.destroy, width=10, height=2,
              font=("Microsoft YaHei", 10)).pack(side="left", padx=8)

    root.mainloop()


def run_silent(install_dir=None):
    if not install_dir:
        install_dir = find_install_dir()
    logs = []
    if not install_dir:
        logs.append("RESULT=FAIL: 未检测到已安装的风语")
        try:
            (Path(os.environ.get("TEMP", ".")) / "fengyu_update.log").write_text(
                "\n".join(logs), encoding="utf-8")
        except Exception:
            pass
        return 1
    logs.append(f"更新目录: {install_dir}")

    def cb(s):
        logs.append(s)
        try:
            print("  " + s)
        except Exception:
            pass

    ok, msgs = do_update(install_dir, cb)
    logs.append(f"RESULT={'OK' if ok else 'FAIL'}")
    try:
        (Path(os.environ.get("TEMP", ".")) / "fengyu_update.log").write_text(
            "\n".join(logs), encoding="utf-8")
    except Exception:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    silent = "--silent" in args
    target = None
    if "--dir" in args:
        i = args.index("--dir")
        if i + 1 < len(args):
            target = args[i + 1]

    if not is_admin():
        print("[提示] 非管理员模式：注册表写 HKCU")

    if silent:
        sys.exit(run_silent(target))
    else:
        run_gui()
