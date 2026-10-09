# 风语 / WindWhisper — 测风塔数据自动化工具 v2.0

## 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10/11 (64位) |
| Python | 3.8+ (推荐 3.11) |
| 依赖软件 | SymphoniePRO Desktop (用于 .rld 解密) |
| 网络 | 能访问 pop.163.com (网易邮箱) |

## 快速安装

### 方式一：使用打包版 exe（推荐）

1. 下载 `风语_v2.0.zip`
2. 解压到任意目录
3. 编辑 `config.json` 填入邮箱授权码和路径
4. 双击 `风语.exe` 运行

### 方式二：从源码运行（开发者）

```bash
# 1. 克隆仓库
git clone https://github.com/zhangyi101/WindWhisper.git
cd WindWhisper

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python main.py
```

### 方式三：一键安装脚本

```bash
# 自动创建虚拟环境 + 安装依赖
install.bat
```

## 配置说明

编辑 `config.json`：

```json
{
  "邮箱": {
    "账号": "your_email@163.com",
    "授权码": "在网易邮箱设置中生成"
  },
  "路径": {
    "测风塔信息表": "C:\\path\\to\\tower_info.xlsx",
    "数据存储目录": "D:\\测风数据文件"
  },
  "解密": {
    "SymphoniePRO路径": "C:\\Program Files (x86)\\Renewable NRG Systems\\SymPRO Desktop\\SymPRODesktop.exe"
  },
  "显示": {
    "字体大小": 10,
    "图标大小": 48,
    "角色头像大小": 72
  }
}
```

## v2.0 新功能

- **动态表头匹配**：Excel 表格列位置变了也能正确读取
- **密码前导零保护**：'0761 格式的密码不再丢失前导零
- **文件菜单**：打开数据目录/塔文件夹/TXT输出/Excel
- **显示设置**：可调节字体大小、图标大小、角色头像大小
- **刷新按钮**：更新表格后点一下即时刷新塔列表
- **定时任务测试**：立即执行一次完整性检测

## 打包命令

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name="风语" ^
  --add-data="resources;resources" ^
  --hidden-import=nrgpy main.py
```

## 技术支持

- GitHub: https://github.com/zhangyi101/WindWhisper
- License: MIT
