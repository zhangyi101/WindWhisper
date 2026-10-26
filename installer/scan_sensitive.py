# -*- coding: utf-8 -*-
"""
敏感信息门禁扫描
打包前强制检查：任何要发布给别人的文件里都不能出现真实凭据。

黑名单来源：
  1. 本机用户配置 %APPDATA%\\风语\\config.json 里的真实账号/授权码
  2. 环境变量中的用户名
  3. 显式列出的自定义敏感词（公司名、项目名等）

用法：
  python installer/scan_sensitive.py            # 扫描安装包目录
  python installer/scan_sensitive.py <path>     # 扫描指定目录
退出码：0=干净，1=发现泄露（打包流程应中止）
"""
import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 允许扫描的文本类文件后缀
TEXT_EXT = {".json", ".md", ".txt", ".template", ".py", ".bat", ".cfg", ".ini", ".yml", ".yaml", ".iss"}

# 额外自定义敏感词（按需补充：公司名、项目名等）
CUSTOM_WORDS = [
    "阳光新能源",
    "禄劝九龙",
    "灌阳项目",
    "灵川项目",
    "东川项目",
    "东兴项目",
    "皎平渡",
    "汤鹰岩",
    "白岩头",
    "雪峰顶",
]


# 扫描时跳过的目录/文件（不是发布内容）
SKIP_DIRS = {"venv", "build", "dist", ".git", "installer_output", "__pycache__", ".idea", ".vscode"}
SKIP_FILES = {"scan_sensitive.py"}  # 本脚本含敏感词黑名单，跳过自身


def collect_secrets():
    """收集必须拦截的真实凭据"""
    secrets = set()

    # 1. 从本机真实配置读取（最关键的：邮箱和授权码）
    cfg = Path(os.environ.get("APPDATA", os.path.expanduser(r"~\AppData\Roaming"))) / "风语" / "config.json"
    if cfg.exists():
        try:
            d = json.loads(cfg.read_text(encoding="utf-8"))
            acct = d.get("邮箱", {}).get("账号", "")
            auth = d.get("邮箱", {}).get("授权码", "")
            if acct and "your_email" not in acct:
                secrets.add(acct)
            if auth and "请在这里" not in auth and len(auth) >= 8:
                secrets.add(auth)
        except Exception:
            pass

    # 2. 环境变量用户名（仅当长度足够避免误报）
    user = os.environ.get("USERNAME", "")
    if len(user) >= 6:
        secrets.add(user)

    # 3. 自定义词
    for w in CUSTOM_WORDS:
        if w:
            secrets.add(w)

    return {s for s in secrets if s and len(s) >= 4}


def scan_path(target: Path, secrets):
    """扫描目录或单个文件，返回 [(文件, 命中词, 行号, 上下文)]"""
    hits = []

    if target.is_file():
        files = [target]
    else:
        files = []
        for p in target.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in TEXT_EXT:
                continue
            if p.name in SKIP_FILES:
                continue
            # 跳过 venv/build/.git 等目录
            parts = {x.lower() for x in p.parts}
            if parts & SKIP_DIRS:
                continue
            files.append(p)

    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for s in secrets:
                if s in line:
                    hits.append((str(f), s, line_no, line.strip()[:120]))
    return hits


def scan_exe_strings(exe_path: Path, secrets):
    """粗扫 exe 内嵌字符串（只查邮箱和授权码这类强特征）"""
    hits = []
    if not exe_path.exists():
        return hits
    try:
        data = exe_path.read_bytes()
    except Exception:
        return hits
    # 只扫强特征（邮箱格式、16位授权码）
    strong = [s for s in secrets if "@" in s or len(s) >= 12]
    for s in strong:
        if s.encode("utf-8", errors="ignore") in data:
            hits.append((str(exe_path), s, 0, "内嵌字符串命中"))
    return hits


def main():
    targets = sys.argv[1:]
    if targets:
        paths = [Path(t) for t in targets]
    else:
        paths = [ROOT / "安装包_v2.1", ROOT / "dist", ROOT]

    secrets = collect_secrets()
    print("=" * 60)
    print("敏感信息门禁扫描")
    print("=" * 60)
    print(f"待拦截特征数: {len(secrets)}")
    for s in secrets:
        masked = s if len(s) <= 4 else (s[:2] + "*" * (len(s) - 4) + s[-2:])
        print(f"  · {masked}")
    print()

    all_hits = []
    for p in paths:
        if not p.exists():
            continue
        print(f"扫描: {p}")
        # 安装包目录：文本 + exe
        hits = scan_path(p, secrets)
        all_hits.extend(hits)
        if p.name.startswith("安装包"):
            for exe in p.glob("*.exe"):
                hits2 = scan_exe_strings(exe, secrets)
                all_hits.extend(hits2)
                print(f"  {exe.name}: {'❌ 发现泄露' if hits2 else '✅ 干净'}")

        # 特别检查：不该存在任何真实 config.json
        for bad in p.rglob("config.json"):
            all_hits.append((str(bad), "存在真实 config.json 文件", 0, "必须删除"))

    print()
    if all_hits:
        print("=" * 60)
        print(f"❌ 发现 {len(all_hits)} 处敏感信息，禁止打包！")
        print("=" * 60)
        for f, s, line, ctx in all_hits:
            print(f"  {f}")
            if line:
                print(f"    行 {line}: {ctx}")
            else:
                print(f"    {ctx}")
        return 1

    print("=" * 60)
    print("✅ 扫描通过：没有发现任何真实凭据")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
