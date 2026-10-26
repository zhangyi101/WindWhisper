# -*- coding: utf-8 -*-
"""
组装完整安装包文件夹 — 确保复制到任何 Windows 电脑都能安装使用

产出： D:\\WindWatcher\\安装包_v2.1\\
    风语_安装.exe       ← 双击即可安装（内嵌全部程序与资源）
    风语_更新.exe       ← 更新/修复（保留配置）
    风语_卸载.exe       ← 卸载（可选保留配置）
    安装说明.txt        ← 给人看的说明
    config.json.template← 配置模板参考（安装时会自动生成 config.json）
    README.md           ← 项目说明
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
OUT_INSTALLERS = ROOT / "installer_output"
PKG = ROOT / "安装包_v2.1"

README_TXT = """============================================================
  风语 / WindWhisper v2.1 — 测风塔数据自动化工具
  安装说明
============================================================

【一、这是什么】
  从网易邮箱自动下载测风塔原始数据(.rld)，按塔号归档，
  调用 nrgpy / SymphoniePRO Desktop 解密为可读 .txt，
  供 Windographer 等工具直接导入。

【二、安装步骤】
  1. 把整个「安装包_v2.1」文件夹复制到目标电脑（任意位置）
  2. 双击  风语_安装.exe
     · 如弹出 UAC 提示，点「是」（需要管理员权限写入 Program Files）
     · 默认安装到  C:\\Program Files\\风语
     · 可点「浏览」改到 D 盘等位置
  3. 点「开始安装」，等待完成
  4. 桌面会出现快捷方式「风语」，双击即可运行

【三、安装后会得到什么】
  · 安装目录（默认 C:\\Program Files\\风语）
      风语.exe            主程序（已内置 Python 运行环境，无需另装 Python）
      resources\\          主题皮肤、角色头像、台词
      config.json         配置文件（首次由模板生成）
      风语_更新.exe        更新/修复程序
      风语_卸载.exe        卸载程序
  · 桌面快捷方式「风语」
  · 控制面板 → 程序和功能 中可见「风语」，可「修改」或「卸载」

【四、首次使用前的配置】
  打开软件 → 「⚙ 配置」标签页，填写：
    · 邮箱账号 + 授权码（网易邮箱 → 设置 → POP3/SMTP/IMAP → 生成授权码）
    · 测风塔信息表路径（你的 Excel 文件）
    · 数据存储目录（默认 D:\\测风数据文件）
    · SymphoniePRO 路径（点「自动检测」可自动找）

  填完点「🔗 测试邮箱连接」验证，成功后再点「💾 保存配置」。

  ★ 配置文件位置：%APPDATA%\\风语\\config.json
    （即 C:\\Users\\你的用户名\\AppData\\Roaming\\风语\\config.json）
    放在这里是因为安装目录（Program Files）普通用户没有写权限，
    配置存用户目录才能正常保存。

  本安装包不含任何邮箱账号或授权码，每个使用者填自己的。

  Excel 表格只需包含表头：测风塔编号 / 所属项目 / 密码（数据解析密码）
  列的位置随意，程序按表头名自动识别。

【五、必须另装的第三方软件】
  ⚠ SymphoniePRO Desktop（NRG Systems 官方软件）
     用途：解密 .rld 原始数据文件（nrgpy 需要调用它）
     下载：https://www.renewablenrgsystems.com/
     说明：这是厂商商业软件，无法打包进本安装包。
           不装的话：下载功能正常，但无法把 .rld 转成 .txt。

【六、升级 / 修复】
  双击 风语_更新.exe
    · 会自动从注册表找到已安装位置
    · 覆盖程序文件与资源
    · 你的 config.json（邮箱授权码等）会被完整保留
  也可以在 控制面板 → 程序和功能 → 风语 → 更改(修改) 调用。

【七、卸载】
  双击 风语_卸载.exe
    · 删除程序文件、桌面快捷方式、注册表项
    · 会询问是否保留 config.json（建议保留，方便以后重装）
    · 不会删除测风数据目录（D:\\测风数据文件）和 SymphoniePRO Desktop
  也可以在 控制面板 → 程序和功能 → 风语 → 卸载。

【八、常见问题】
  Q: 安装时提示需要管理员权限？
  A: 右键 风语_安装.exe → 以管理员身份运行。

  Q: 提示风语.exe 正在运行，无法更新？
  A: 先关闭风语主程序，再运行更新。

  Q: 换了电脑，测风数据要重新下载吗？
  A: 程序会检查本地已有 .rld，只下载缺失的部分。
     如果想带走数据，把 D:\\测风数据文件 整个文件夹复制过去即可。

  Q: 角色头像想换？
  A: 打开安装目录\\resources\\icons\\
     · characters\\   放 PNG 头像（覆盖同名文件即换图）
     · characters.cfg 写「文件名=显示名」映射
     · quotes.txt     写「角色名：台词」，每人可多行
     改完重启程序生效，不需要改代码。

============================================================
  版本：v2.1.0
  打包时间：{build_time}
============================================================
"""


def main():
    if not OUT_INSTALLERS.exists():
        print(f"[ERROR] 找不到安装程序输出目录: {OUT_INSTALLERS}")
        return 1

    if PKG.exists():
        shutil.rmtree(str(PKG), ignore_errors=True)
    PKG.mkdir(parents=True, exist_ok=True)

    # 1. 三个安装程序
    needed = ["风语_安装.exe", "风语_更新.exe", "风语_卸载.exe"]
    missing = []
    for name in needed:
        src = OUT_INSTALLERS / name
        if not src.exists():
            missing.append(name)
            continue
        shutil.copy2(str(src), str(PKG / name))
        print(f"  + {name}  ({src.stat().st_size/1024/1024:.1f} MB)")

    if missing:
        print(f"[ERROR] 缺少安装程序: {missing}")
        return 1

    # 2. 说明文档
    build_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    readme = PKG / "安装说明.txt"
    readme.write_text(README_TXT.format(build_time=build_time), encoding="utf-8-sig")
    print(f"  + 安装说明.txt")

    for doc in ("README.md", "config.json.template"):
        src = ROOT / doc
        if src.exists():
            shutil.copy2(str(src), str(PKG / doc))
            print(f"  + {doc}")

    # 3. 校验
    print(f"\n{'='*60}")
    print(f"安装包已生成: {PKG}")
    print(f"{'='*60}")
    total = 0
    for f in sorted(PKG.iterdir()):
        size = f.stat().st_size
        total += size
        print(f"  {f.name:28s} {size/1024/1024:8.1f} MB")
    print(f"  {'合计':28s} {total/1024/1024:8.1f} MB")

    # 4. 发布前最后一道门禁：扫描成品目录 + exe 内嵌字符串
    print(f"\n{'='*60}\n发布前敏感信息扫描\n{'='*60}")
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "scan_sensitive.py"), str(PKG)],
        cwd=str(ROOT)
    )
    if r.returncode != 0:
        print("\n[ABORT] 安装包内含真实凭据，已删除该安装包，禁止发布！")
        shutil.rmtree(str(PKG), ignore_errors=True)
        return 1

    print("\n✅ 安装包干净，可以发布。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
