# 风语 / WindWhisper — 安装包制作指南

## 三件套方案

遵循标准软件安装规范，提供三个独立 exe：

| exe 文件 | 用途 | 行为 |
|---|---|---|
| `风语_安装.exe` | 首次安装 | 全新安装，创建桌面快捷方式，写入注册表 |
| `风语_更新.exe` | 更新/修复 | 覆盖程序文件，**保留 config.json 和数据** |
| `风语_卸载.exe` | 卸载 | 删除程序，**询问是否保留配置和数据** |

## 制作方法

### 使用 Inno Setup（推荐）

1. 下载安装 Inno Setup: https://jrsoftware.org/download.php/is.exe
2. 用 Inno Setup Compiler 打开 `installer.iss`
3. 编译，自动生成安装包

### 三个 exe 的区别

Inno Setup 编译参数控制：

```
# 安装版（默认）
iscc installer.iss /DOUTPUT_TYPE=INSTALL

# 更新版（不覆盖 config.json，不创建快捷方式）
iscc installer.iss /DOUTPUT_TYPE=UPDATE

# 卸载版（独立卸载器）
iscc uninstaller.iss
```

### 注意事项

- **Python 环境**：安装包不含 Python（太大），INSTALL.md 提供下载地址
- **SymphoniePRO Desktop**：需用户单独安装（NRG Systems 官网）
- **config.json**：安装版用 template 创建，更新版保留现有
- **测风数据**：数据目录在 `D:\测风数据文件`，不在程序目录下，卸载不影响
