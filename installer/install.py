# -*- coding: utf-8 -*-
"""
风语_安装.exe — 首次安装程序 (GUI)

功能：
  1. 图形界面选择安装目录
  2. 复制 风语.exe + resources + config.json.template
  3. 复制 风语_更新.exe / 风语_卸载.exe 到安装目录
  4. 创建桌面快捷方式「风语」
  5. 写入注册表卸载信息（控制面板可见）

命令行：
  风语_安装.exe               → GUI 模式
  风语_安装.exe --silent      → 静默安装到默认路径
  风语_安装.exe --silent --dir "D:\\xxx"  → 静默安装到指定路径
"""
import os
import sys
import shutil
import ctypes
import subprocess
import tempfile
import time
from pathlib import Path
import winreg

APP_NAME = "风语"
APP_VERSION = "2.1.0"
APP_PUBLISHER = "WindWhisper"
def get_default_install_dir():
    """有管理员权限 → Program Files；否则 → 用户目录（免 UAC）"""
    try:
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        admin = False
    if admin:
        return os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), APP_NAME)
    return os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")),
        "Programs", APP_NAME
    )


DEFAULT_INSTALL_DIR = get_default_install_dir()
UNINSTALL_KEY = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"

# PyInstaller 内嵌资源目录
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = Path(__file__).resolve().parent


def _find_file(name):
    """
    查找随附文件：先查 PyInstaller 内嵌目录，再查 exe 所在目录（安装包文件夹）。
    这样更新/卸载程序可以作为同目录文件分发，不必内嵌进安装程序（省体积）。
    """
    p = BUNDLE_DIR / name
    if p.exists():
        return p
    # exe 所在目录
    if getattr(sys, 'frozen', False):
        p2 = Path(sys.executable).resolve().parent / name
        if p2.exists():
            return p2
    # 开发模式：上级目录
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
    """以管理员权限重启自身"""
    script = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    if not getattr(sys, 'frozen', False):
        params = f'"{sys.argv[0]}" {params}'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", script, params, None, 1)
    if ret <= 32:
        ctypes.windll.user32.MessageBoxW(
            0, "需要管理员权限才能安装到 Program Files。\n请右键 → 以管理员身份运行。",
            f"{APP_NAME} 安装", 0x10
        )
    sys.exit(0)


def get_desktop_dirs():
    """返回所有可能的桌面目录（用户桌面 + 公共桌面）"""
    dirs = []
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        d = Path(userprofile) / "Desktop"
        if d.exists():
            dirs.append(d)
    # 公共桌面（中文系统可能是 公共\桌面）
    public = os.environ.get("PUBLIC", r"C:\Users\Public")
    for name in ("Desktop", "桌面"):
        d = Path(public) / name
        if d.exists() and d not in dirs:
            dirs.append(d)
    return dirs


def create_shortcut(install_path, shortcut_name=APP_NAME):
    """
    用 PowerShell 创建桌面快捷方式（不依赖 pywin32，更可靠）
    返回 (success, message)
    """
    target = install_path / "风语.exe"
    if not target.exists():
        return False, f"目标程序不存在: {target}"

    desktops = get_desktop_dirs()
    if not desktops:
        return False, "找不到桌面目录"

    created = []
    errors = []
    for desktop in desktops:
        lnk = desktop / f"{shortcut_name}.lnk"
        # PowerShell 脚本（写临时文件，避免转义问题）
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
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".ps1", delete=False, encoding="utf-8-sig"
            ) as f:
                f.write(ps)
                ps_path = f.name
            r = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path],
                capture_output=True, text=True, timeout=30
            )
            os.unlink(ps_path)
            if lnk.exists():
                created.append(str(lnk))
            else:
                errors.append(f"{lnk}: {r.stderr.strip()[:100]}")
        except Exception as e:
            errors.append(f"{desktop}: {e}")

    if created:
        return True, "已创建: " + "; ".join(created)
    return False, "; ".join(errors) if errors else "未知错误"


def remove_shortcut(shortcut_name=APP_NAME):
    """删除桌面快捷方式"""
    removed = []
    for desktop in get_desktop_dirs():
        lnk = desktop / f"{shortcut_name}.lnk"
        if lnk.exists():
            try:
                lnk.unlink()
                removed.append(str(lnk))
            except Exception:
                pass
    return removed


def write_registry(install_dir):
    """
    写注册表卸载信息。
    优先 HKLM（控制面板对所有用户可见）；没有管理员权限时降级 HKCU。
    返回 (success, message, hive_used)
    """
    install_path = Path(install_dir)
    exe_path = str(install_path / "风语.exe")
    uninstall_exe = str(install_path / "风语_卸载.exe")
    update_exe = str(install_path / "风语_更新.exe")

    def _write(hive, hive_name):
        key = winreg.CreateKey(hive, UNINSTALL_KEY)
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_path))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe_path)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}"')
        winreg.SetValueEx(key, "ModifyPath", 0, winreg.REG_SZ, f'"{update_exe}"')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 0)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        return hive_name

    # 1. 尝试 HKLM
    try:
        hive = _write(winreg.HKEY_LOCAL_MACHINE, "HKLM")
        return True, f"注册表写入成功（{hive}，所有用户可见）", hive
    except PermissionError:
        pass
    except Exception:
        pass

    # 2. 降级 HKCU
    try:
        hive = _write(winreg.HKEY_CURRENT_USER, "HKCU")
        return True, f"注册表写入成功（{hive}，当前用户可见）", hive
    except Exception as e:
        return False, f"注册表写入失败: {e}", None


def do_install(install_dir, progress_cb=None):
    """
    执行安装。返回 (success, messages_list)
    progress_cb(str) 用于 GUI 显示进度
    """
    msgs = []

    def log(s):
        msgs.append(s)
        if progress_cb:
            progress_cb(s)

    install_path = Path(install_dir)
    try:
        install_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, [f"无法创建安装目录: {e}"]

    # 1. 风语.exe
    exe_src = BUNDLE_DIR / "风语.exe"
    if not exe_src.exists():
        return False, [f"安装包损坏：找不到 风语.exe（{exe_src}）"]
    log("复制 风语.exe ...")
    try:
        shutil.copy2(str(exe_src), str(install_path / "风语.exe"))
    except Exception as e:
        return False, msgs + [f"复制主程序失败（是否正在运行？）: {e}"]

    # 2. resources/
    res_src = BUNDLE_DIR / "resources"
    if res_src.exists():
        log("复制 resources/ ...")
        res_dst = install_path / "resources"
        if res_dst.exists():
            shutil.rmtree(str(res_dst), ignore_errors=True)
        try:
            shutil.copytree(str(res_src), str(res_dst))
        except Exception as e:
            return False, msgs + [f"复制资源失败: {e}"]

    # 3. config.json（优先从上次卸载的备份恢复）
    cfg_dst = install_path / "config.json"
    if not cfg_dst.exists():
        backup = Path(os.environ.get(
            "LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")
        )) / APP_NAME / "config.json.bak"
        tpl = _find_file("config.json.template")
        if backup.exists():
            log("发现上次卸载的配置备份，正在恢复 ...")
            try:
                shutil.copy2(str(backup), str(cfg_dst))
                log(f"  已恢复配置: {backup}")
            except Exception as e:
                log(f"  [警告] 恢复备份失败: {e}")
        elif tpl:
            log("创建 config.json ...")
            shutil.copy2(str(tpl), str(cfg_dst))
    else:
        log("config.json 已存在，保留用户配置")

    # 4. 更新/卸载程序（供控制面板「修改」「卸载」调用）
    for sub in ("风语_更新.exe", "风语_卸载.exe"):
        src = _find_file(sub)
        if src:
            log(f"复制 {sub} ...")
            try:
                shutil.copy2(str(src), str(install_path / sub))
            except Exception as e:
                log(f"  [警告] {sub} 复制失败: {e}")
        else:
            log(f"  [提示] 未找到 {sub}（请确保它与安装程序在同一文件夹）")

    # 5. 说明文档
    for doc in ("INSTALL.md", "README.md", "PACKAGING.md"):
        src = _find_file(doc)
        if src:
            try:
                shutil.copy2(str(src), str(install_path / doc))
            except Exception:
                pass

    # 6. 桌面快捷方式
    log("创建桌面快捷方式 ...")
    ok, msg = create_shortcut(install_path)
    log(msg if ok else f"快捷方式警告: {msg}")

    # 7. 注册表
    log("写入注册表 ...")
    ok2, msg2, _hive = write_registry(install_dir)
    log(msg2)

    return True, msgs


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(f"{APP_NAME} 安装程序 v{APP_VERSION}")
    root.geometry("640x620")
    root.minsize(620, 600)
    root.resizable(False, True)

    # ===== 顶部标题区 =====
    header = tk.Frame(root)
    header.pack(side="top", fill="x", pady=(16, 0))
    tk.Label(header, text=f"{APP_NAME} (WindWhisper)",
             font=("Microsoft YaHei", 16, "bold")).pack()
    tk.Label(header, text="测风塔数据自动化工具 · 安装程序",
             font=("Microsoft YaHei", 9), fg="#666").pack(pady=(2, 0))

    # ===== 底部按钮区（先占位，避免被内容挤掉）=====
    btn_frame = tk.Frame(root)
    btn_frame.pack(side="bottom", fill="x", pady=14)

    # ===== 中间内容区 =====
    frame = tk.Frame(root, padx=20, pady=8)
    frame.pack(side="top", fill="both", expand=True)

    # 安装路径
    path_row = tk.Frame(frame)
    path_row.pack(fill="x", pady=(6, 4))
    tk.Label(path_row, text="安装目录：", font=("Microsoft YaHei", 10)).pack(side="left")
    path_var = tk.StringVar(value=DEFAULT_INSTALL_DIR)
    tk.Entry(path_row, textvariable=path_var, width=42,
             font=("Consolas", 9)).pack(side="left", fill="x", expand=True, padx=(0, 6))

    def browse():
        d = filedialog.askdirectory(title="选择安装目录", initialdir=path_var.get())
        if d:
            path_var.set(os.path.normpath(d))

    tk.Button(path_row, text="浏览...", command=browse, width=7).pack(side="left")

    # 说明
    info = (
        "安装内容：\n"
        "  · 风语.exe 主程序（已内置 Python 运行环境，无需另装）\n"
        "  · resources/ 主题与角色头像\n"
        "  · config.json 配置文件模板\n"
        "  · 更新/卸载程序（控制面板「修改」「卸载」可用）\n"
        "  · 将在桌面创建快捷方式「风语」"
    )
    info_label = tk.Label(frame, text=info, justify="left", anchor="w",
                          font=("Microsoft YaHei", 9), fg="#333")
    info_label.pack(fill="x", pady=(8, 4))

    warn_label = tk.Label(
        frame,
        text="注意：解密 .rld 文件需另装 SymphoniePRO Desktop（NRG 官方软件）",
        justify="left", anchor="w", font=("Microsoft YaHei", 8), fg="#b26a00")
    warn_label.pack(fill="x", pady=(0, 8))

    # 进度日志
    tk.Label(frame, text="安装进度：", font=("Microsoft YaHei", 9),
             anchor="w").pack(fill="x")
    log_box = tk.Text(frame, height=8, font=("Consolas", 8), state="disabled",
                      bg="#f7f7f7", relief="solid", borderwidth=1, wrap="word")
    log_box.pack(fill="both", expand=True, pady=(2, 6))

    def append_log(text):
        log_box.config(state="normal")
        log_box.insert("end", text + "\n")
        log_box.see("end")
        log_box.config(state="disabled")
        root.update_idletasks()

    def start_install():
        target = path_var.get().strip()
        if not target:
            messagebox.showwarning("提示", "请填写安装目录")
            return
        target = os.path.abspath(os.path.expandvars(target))

        # 目录非空时确认
        if os.path.isdir(target) and os.listdir(target):
            existing_exe = Path(target) / "风语.exe"
            if existing_exe.exists():
                if not messagebox.askyesno("已安装", f"该目录已有风语程序：\n{target}\n\n是否覆盖安装（保留 config.json）？"):
                    return
            else:
                if not messagebox.askyesno("目录非空", f"目录非空：\n{target}\n\n继续安装？"):
                    return

        install_btn.config(state="disabled")
        browse_btn.config(state="disabled")
        append_log(f"开始安装到: {target}")

        ok, msgs = do_install(target, append_log)
        if ok:
            append_log("─" * 40)
            append_log("安装完成！")
            messagebox.showinfo("安装完成",
                                f"{APP_NAME} 已安装到：\n{target}\n\n"
                                f"桌面快捷方式：{APP_NAME}\n"
                                f"卸载方式：控制面板 → 程序和功能 → {APP_NAME}")
            root.destroy()
        else:
            append_log("安装失败")
            messagebox.showerror("安装失败", "\n".join(msgs[-3:]))
            install_btn.config(state="normal")
            browse_btn.config(state="normal")

    inner_btn = tk.Frame(btn_frame)
    inner_btn.pack()  # 居中
    install_btn = tk.Button(inner_btn, text="开始安装", command=start_install,
                            width=16, height=2, bg="#2e7d32", fg="white",
                            font=("Microsoft YaHei", 10, "bold"))
    install_btn.pack(side="left", padx=8)
    browse_btn = tk.Button(inner_btn, text="取消", command=root.destroy,
                           width=10, height=2, font=("Microsoft YaHei", 10))
    browse_btn.pack(side="left", padx=8)

    root.mainloop()


def run_silent(install_dir):
    """静默安装（测试用）。windowed 程序无控制台，结果写入日志文件。"""
    logs = [f"目标目录: {install_dir}"]

    def cb(s):
        logs.append(s)
        try:
            print("  " + s)
        except Exception:
            pass

    ok, msgs = do_install(install_dir, cb)
    logs.append(f"RESULT={'OK' if ok else 'FAIL'}")
    try:
        log_path = Path(os.environ.get("TEMP", ".")) / "fengyu_install.log"
        log_path.write_text("\n".join(logs), encoding="utf-8")
    except Exception:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    silent = "--silent" in args
    target_dir = DEFAULT_INSTALL_DIR
    if "--dir" in args:
        idx = args.index("--dir")
        if idx + 1 < len(args):
            target_dir = args[idx + 1]

    if not is_admin():
        print("[提示] 非管理员模式：可安装到 D 盘/用户目录；装 Program Files 需右键以管理员身份运行")

    if silent:
        sys.exit(run_silent(target_dir))
    else:
        run_gui()
