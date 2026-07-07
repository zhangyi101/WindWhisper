# 🌬️ 风语 / WindWhisper

**测风塔数据全自动流水线** — 从网易邮箱自动下载测风塔原始数据 (.rld)，按塔号归档，调用 nrgpy / SymphoniePRO Desktop 解密为可读 .txt 格式。

English: *Automated wind tower data pipeline — POP3 email download → nrgpy decryption → TXT archiving. Desktop GUI + CLI.*

---

## 📋 项目简介 / Overview

风语 (WindWhisper) 是一款面向测风数据工程师的桌面自动化工具。它解决了测风塔日常运维中最繁琐的环节：每天手动登录邮箱下载附件、逐个解密 .rld 文件、手动合并整理。

**完整链路 / Full Pipeline:**

```
📧 POP3 登录网易邮箱
    ↓ 按日期范围筛选邮件
    ↓ 按塔号前缀匹配附件
📂 下载 .rld → 按塔号自动归档
    ↓
🔐 nrgpy / SymphoniePRO Desktop 解密
    ↓ 临时目录 → 合并去重
    ↓ 按日期范围筛选数据行
📄 TXT合并输出 → TXT输出/ 子目录
```

---

## ✨ 功能特性 / Features

### 🖥️ 桌面版 GUI + ⌨️ CLI 双模式
- **桌面版 (PyQt5):** 可视化界面，项目树选择、日期选择器、进度条、日志面板一应俱全
- **CLI 模式:** 核心引擎 (core/) 无界面依赖，可集成到定时任务或脚本中

### 🧠 智能本地完整性检测
- 扫描本地 .rld 文件，自动比对预期日期范围
- 精确报告缺失天数，**按需增量下载** — 不重复下载已有文件
- 结果一目了然：✅ 完整 / ⚠ 缺 N 天

### 🎨 5 套 QSS 主题
| 主题名称 | 文件名 | 风格 |
|---------|--------|------|
| 念头通达 (凡人修仙传) | `fanren_xiuxian.qss` | 深翠绿·掌天瓶 |
| 暗夜科技 | `dark_tech.qss` | 深色·霓虹 |
| 浅紫天蓝 | `ocean_blue.qss` | 柔和·天空 |
| 极简亮色 | `clean_light.qss` | 亮白·办公 |
| 枫叶银杏 (灵笼) | `lingcage.qss` | 暖橙·末世 |

### 👥 12 角色图标系统
来自凡人修仙传的 12 个角色，每个角色有 5 条悬停随机台词：
韩立、银月、南宫婉、紫灵、柳玉、宋玉、燕如焉、元瑶、啼魂、梅凝、玄骨、慕沛灵

### ⚡ 增量处理
- 下载环节：已存在的文件自动跳过
- 解密环节：已有 `_meas.txt` 的自动跳过
- 合并环节：按日期范围筛选数据行，避免重复

### ⏰ 定时任务支持
内建 Windows 任务计划程序集成，可设置每月任意日期自动执行

---

## 🚀 快速开始 / Quick Start

### 依赖安装 / Dependencies

```bash
# Python 3.8+ 推荐 3.11
pip install pyqt5 nrgpy openpyxl pywin32
```

> **注意:** nrgpy 需要在安装了 [SymphoniePRO Desktop](https://www.renewablenrgsystems.com/) 的 Windows 电脑上才能执行解密。

### 配置 / Configuration

1. 复制配置模板并填入真实信息：

```bash
cp config.json.template config.json
```

2. 编辑 `config.json`：

```json
{
  "邮箱": {
    "账号": "your_email@163.com",
    "授权码": "your_pop3_authorization_code"
  },
  "路径": {
    "测风塔信息表": "C:\Path\To\Tower_Info.xlsx",
    "数据存储目录": "D:\WindData"
  },
  "解密": {
    "SymphoniePRO路径": "C:\Program Files (x86)\Renewable NRG Systems\SymPRO Desktop\SymPRODesktop.exe"
  }
}
```

> **获取授权码:** 登录 163 邮箱 → 设置 → POP3/SMTP/IMAP → 开启 POP3 → 新增授权码

### CLI 用法示例 / CLI Usage

```python
from core.config_loader import Config
from core.executor import TaskExecutor
from datetime import datetime, timedelta

# 加载配置
config = Config("config.json")

# 获取塔列表
towers = config.get_tower_list()

# 执行任务（过去 30 天）
executor = TaskExecutor(config)
end = datetime.now()
start = end - timedelta(days=30)
report = executor.run(towers, start, end)

print(report)
```

### 桌面版启动 / Desktop GUI

```bash
python main.py
```

### 打包为 exe / Build

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name="风语" \
  --add-data="resources;resources" \
  --hidden-import=nrgpy main.py
```

输出在 `dist/风语.exe`。

---

## 🖼️ 桌面版截图 / Screenshots

*（截图待添加 — 主窗口包含：项目树、日期选择器、进度条、深色日志面板、角色头像栏）*

---

## 🏗️ 项目结构 / Project Structure

```
WindWatcher/
├── main.py                  ← 入口（PyQt5 桌面版）
├── config.json              ← 用户配置（已 .gitignore，不推送）
├── config.json.template     ← 配置模板
├── build.bat                ← PyInstaller 打包脚本
├── core/                    ← 核心引擎（无界面依赖）
│   ├── config_loader.py     ← 配置 + Excel 塔信息加载
│   ├── integrity_checker.py ← 本地数据完整性检查
│   ├── email_fetcher.py     ← POP3 邮箱登录/扫描/下载
│   ├── converter.py         ← .rld 解密转换（nrgpy + 合并）
│   └── executor.py          ← 任务编排引擎
├── ui/
│   └── main_window.py       ← PyQt5 主窗口 + 所有面板 + 角色栏
├── resources/
│   ├── themes/              ← 5 套 QSS 主题文件
│   └── icons/
│       ├── characters/      ← 12 个角色头像 PNG
│       └── quotes.txt      ← 角色台词库
├── .gitignore
├── LICENSE                  ← MIT
└── README.md                ← 本文件
```

---

## 🛠️ 技术栈 / Tech Stack

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.8+ |
| GUI | PyQt5 |
| 邮箱协议 | POP3/SSL (端口 995) |
| 解密引擎 | nrgpy + SymphoniePRO Desktop |
| Excel 读取 | openpyxl |
| 打包 | PyInstaller |
| 定时任务 | Windows Task Scheduler (pywin32) |

---

## 📜 许可证 / License

[MIT](LICENSE) © 2025 zhangyi101

---

## 🙏 致谢 / Acknowledgements

- [Renewable NRG Systems](https://www.renewablenrgsystems.com/) — SymphoniePRO 数据平台
- [nrgpy](https://pypi.org/project/nrgpy/) — Python 解密库
