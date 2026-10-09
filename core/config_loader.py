"""
配置加载模块
读取 config.json（用户配置）+ Excel 表格（塔信息）
所有配置集中管理，其他模块通过此模块获取配置

v2.0 改进：
- 按表头名称动态匹配列，不再硬编码列索引
- 密码列支持文本前缀（'0761）和数字格式，保留前导零
- 增加刷新机制，支持运行中重新加载 Excel
"""
import json
import os
import sys
from datetime import datetime, timedelta


# ============================================================
# 表头别名映射 — 每个字段可能有多种表头叫法
# 匹配规则：先精确匹配，再子串匹配；排除关键词优先级最高
# ============================================================
COLUMN_ALIASES = {
    "tower_code": ["编号", "塔编号", "测风塔编号", "full_code", "full code"],
    "project": ["项目", "所属项目", "项目名称", "项目名"],
    "start_date": ["测风起始", "起始时间", "开始时间", "设立日期", "安装日期", "起始"],
    "short_code": ["塔号", "短号", "编号short", "short"],
    "decrypt_pwd": ["解析密码", "数据解析密码", "解密密码", "密码", "password"],
    "note": ["备注", "说明", "状态备注"],
}

# 排除关键词：如果表头包含这些词，则不匹配到对应字段
# 例如 "邮箱密码" 包含 "邮箱"，不匹配到 decrypt_pwd
COLUMN_EXCLUSIONS = {
    "decrypt_pwd": ["邮箱", "mail", "email", "登录"],
    "note": ["邮箱", "密码", "风速", "通道"],
}

# 必需列：缺失则报警告但仍继续（用默认值）
REQUIRED_COLUMNS = ["tower_code", "project", "decrypt_pwd"]

# 可选列：缺失时用默认值
OPTIONAL_COLUMNS = ["start_date", "short_code", "note"]


def get_default_config_path():
    """获取 config.json 的默认路径（与 exe 同目录）"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config.json")


class Config:
    """全局配置管理器，加载 config.json + Excel 表格"""

    def __init__(self, config_path=None):
        self.config_path = config_path or get_default_config_path()
        self.data = self._load_config()
        self.excel_path = self._resolve_path(self.data.get("路径", {}).get("测风塔信息表", ""))
        self.data_root = self._resolve_path(self.data.get("路径", {}).get("数据存储目录", ""))
        self.mail_account = self.data.get("邮箱", {}).get("账号", "")
        self.mail_auth = self.data.get("邮箱", {}).get("授权码", "")
        self.sympro_path = self._resolve_path(
            self.data.get("解密", {}).get("SymphoniePRO路径",
                r"C:\Program Files (x86)\Renewable NRG Systems\SymPRO Desktop\SymPRODesktop.exe"
            )
        )
        # 显示设置（字体/图标大小）
        display = self.data.get("显示", {})
        self.font_size = display.get("字体大小", 10)
        self.icon_size = display.get("图标大小", 48)
        self.char_icon_size = display.get("角色头像大小", 72)

    def _load_config(self):
        """读取 config.json"""
        if not os.path.exists(self.config_path):
            return self._create_default_config()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"配置文件读取失败: {e}")
            return self._create_default_config()

    def _create_default_config(self):
        """如果 config.json 不存在，创建默认模板（不含真实账号）"""
        default = {
            "邮箱": {
                "账号": "your_email@163.com",
                "授权码": "请在这里填写网易邮箱授权码"
            },
            "路径": {
                "测风塔信息表": "",
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
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            print(f"已创建默认配置文件: {self.config_path}")
        except Exception:
            pass
        return default

    def save(self):
        """保存当前配置到文件"""
        self.data["邮箱"] = {
            "账号": self.mail_account,
            "授权码": self.mail_auth
        }
        self.data["路径"] = {
            "测风塔信息表": self.excel_path,
            "数据存储目录": self.data_root
        }
        self.data["解密"] = {
            "SymphoniePRO路径": self.sympro_path
        }
        self.data["显示"] = {
            "字体大小": self.font_size,
            "图标大小": self.icon_size,
            "角色头像大小": self.char_icon_size
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _resolve_path(self, path):
        """解析路径，支持环境变量和相对路径"""
        if not path:
            return ""
        path = os.path.expandvars(path)
        path = os.path.expanduser(path)
        return os.path.abspath(path)

    # ============================================================
    # Excel 表头动态匹配
    # ============================================================

    def _build_column_map(self, ws):
        """
        扫描表头行（第1行），建立 {字段名: 列索引} 映射。
        
        匹配规则（按优先级）：
        1. 精确匹配：表头 == 别名（忽略大小写和空格）→ 最高优先
        2. 子串匹配：别名 in 表头（忽略大小写和空格）→ 次优先
        3. 排除规则：表头包含排除关键词的字段不匹配
        
        支持合并单元格：如果某个表头单元格为空，沿用左侧非空值。
        """
        # 读取第1行所有单元格的文本
        headers = []
        for cell in ws[1]:
            val = cell.value
            if val is not None:
                headers.append(str(val).strip())
            else:
                headers.append("")  # 合并单元格右侧通常为 None

        # 前向填充空表头（处理合并单元格）
        last_non_empty = ""
        for i, h in enumerate(headers):
            if h:
                last_non_empty = h
            else:
                headers[i] = last_non_empty

        # 构建映射：两轮匹配
        col_map = {}
        
        # 第1轮：精确匹配（优先级高）
        for field, aliases in COLUMN_ALIASES.items():
            aliases_norm = [a.lower().replace(" ", "") for a in aliases]
            exclusions = [e.lower() for e in COLUMN_EXCLUSIONS.get(field, [])]
            for col_idx, header in enumerate(headers):
                if col_idx in [v for v in col_map.values()]:
                    continue  # 此列已被匹配
                header_norm = header.lower().replace(" ", "")
                # 检查排除
                if any(ex in header_norm for ex in exclusions):
                    continue
                # 精确匹配
                for alias in aliases_norm:
                    if header_norm == alias:
                        col_map[field] = col_idx
                        break

        # 第2轮：子串匹配（给未匹配的字段补上）
        for field, aliases in COLUMN_ALIASES.items():
            if field in col_map:
                continue  # 已通过精确匹配
            aliases_norm = [a.lower().replace(" ", "") for a in aliases]
            exclusions = [e.lower() for e in COLUMN_EXCLUSIONS.get(field, [])]
            for col_idx, header in enumerate(headers):
                if col_idx in col_map.values():
                    continue  # 此列已被匹配
                header_norm = header.lower().replace(" ", "")
                # 检查排除
                if any(ex in header_norm for ex in exclusions):
                    continue
                # 子串匹配
                for alias in aliases_norm:
                    if alias in header_norm:
                        col_map[field] = col_idx
                        break

        return col_map, headers

    # ============================================================
    # 密码处理 — 保留前导零
    # ============================================================

    @staticmethod
    def _parse_password(raw_value):
        """
        解析密码值，确保保留前导零。

        Excel 中以 '0761 形式录入时，openpyxl 读取为字符串 "0761"。
        如果以数字录入，openpyxl 读取为 int 761，需要补回前导零。
        但我们无法知道原本有几位，所以：
        - 字符串：直接使用（去掉可能的单引号前缀）
        - 数字：转字符串，不加前导零（因为信息已丢失）

        实际上用户说录入的是 '0761（文本格式），所以 openpyxl 会读到 "0761"。
        我们只需要确保不把它转成 int 即可。
        """
        if raw_value is None:
            return ""
        s = str(raw_value).strip()
        # 去掉 Excel 文本前缀单引号（如果存在）
        if s.startswith("'"):
            s = s[1:]
        # 纯数字字符串保持原样（保留前导零）
        # 非纯数字也保持原样
        return s

    # ============================================================
    # 主读取方法
    # ============================================================

    def get_tower_list(self, projects=None):
        """
        从 Excel 读取测风塔信息表，返回有效塔列表。
        v2.0: 按表头名动态匹配列，不再依赖固定列位置。

        返回: list[dict]
            {
                "full_code": "007331",
                "short_code": "7331",
                "project": "禄劝九龙",
                "start_date": datetime 或 None,
                "note": "",
                "decrypt_pwd": "0761"
            }
        """
        import openpyxl

        if not os.path.exists(self.excel_path):
            print(f"找不到Excel文件: {self.excel_path}")
            return []

        try:
            wb = openpyxl.load_workbook(self.excel_path, data_only=True)
        except Exception as e:
            print(f"打开Excel失败: {e}")
            return []

        # 自动查找含"测风"和"总表"的子表（不再限定"华南"）
        sheet_name = None
        for name in wb.sheetnames:
            if "测风" in name and "总表" in name:
                sheet_name = name
                break
        # 退化匹配：只要含"测风"
        if not sheet_name:
            for name in wb.sheetnames:
                if "测风" in name or "塔" in name:
                    sheet_name = name
                    break
        if not sheet_name:
            print(f"找不到测风塔总表子表，可用: {wb.sheetnames}")
            wb.close()
            return []

        ws = wb[sheet_name]

        # 构建表头→列索引映射
        col_map, headers = self._build_column_map(ws)

        # 检查必需列
        missing_required = [f for f in REQUIRED_COLUMNS if f not in col_map]
        if missing_required:
            print(f"⚠ 表格缺少必需列: {missing_required}")
            print(f"  表头为: {headers}")
            print(f"  已匹配列: {col_map}")
            wb.close()
            return []

        # 记录可选列缺失情况
        missing_optional = [f for f in OPTIONAL_COLUMNS if f not in col_map]
        if missing_optional:
            print(f"ℹ 可选列缺失（将用默认值）: {missing_optional}")

        towers = []

        for row in ws.iter_rows(min_row=2, values_only=True):
            # 用映射表取值，不再硬编码列号
            code_raw = self._get_cell(row, col_map, "tower_code")
            if code_raw is None or str(code_raw).strip() == "":
                continue

            project = str(self._get_cell(row, col_map, "project", "")).strip()
            start_serial = self._get_cell(row, col_map, "start_date")
            short_raw = self._get_cell(row, col_map, "short_code")
            note = str(self._get_cell(row, col_map, "note", "")).strip()
            decrypt_pwd = self._parse_password(self._get_cell(row, col_map, "decrypt_pwd"))

            # 过滤未立
            if "未立" in str(code_raw):
                continue

            # 统一编号为6位补零
            full_code = self._pad_code(code_raw)
            if not full_code:
                continue

            # 测风起始时间（可选，缺失时不过滤）
            start_date = self._parse_start_date(start_serial)

            # 短号：有列就用，没有就从全号推导
            if short_raw is not None and str(short_raw).strip():
                if isinstance(short_raw, (int, float)):
                    short_code = str(int(short_raw))
                else:
                    short_code = str(short_raw).strip()
            else:
                short_code = str(int(full_code))

            towers.append({
                "full_code": full_code,
                "short_code": short_code,
                "project": project,
                "start_date": start_date,
                "note": note,
                "decrypt_pwd": decrypt_pwd,
            })

        wb.close()

        # 按项目过滤
        if projects:
            towers = [t for t in towers if t["project"] in projects]

        return towers

    @staticmethod
    def _get_cell(row, col_map, field, default=None):
        """从行数据中按映射取值，越界或缺失返回默认值"""
        idx = col_map.get(field)
        if idx is None or idx >= len(row):
            return default
        val = row[idx]
        return val if val is not None else default

    @staticmethod
    def _pad_code(code):
        """编号统一补零为6位"""
        if code is None:
            return None
        if isinstance(code, (int, float)):
            return f"{int(code):06d}"
        s = str(code).strip()
        # 去掉可能的文本前缀单引号
        if s.startswith("'"):
            s = s[1:]
        if s.isdigit():
            return f"{int(s):06d}"
        return s

    @staticmethod
    def _parse_start_date(raw):
        """解析测风起始时间，支持日期序列号、datetime、字符串"""
        if raw is None:
            return None
        # 已经是 datetime/date
        if isinstance(raw, datetime):
            return raw
        from datetime import date as date_type
        if isinstance(raw, date_type):
            return datetime.combine(raw, datetime.min.time())
        # Excel 日期序列号（数字）
        if isinstance(raw, (int, float)):
            try:
                base = datetime(1899, 12, 30)
                return base + timedelta(days=int(raw))
            except (ValueError, TypeError):
                return None
        # 字符串日期
        s = str(raw).strip()
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"]:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    def get_column_mapping_info(self):
        """
        读取 Excel 并返回表头匹配结果，供 UI 展示。
        返回: dict {matched: {field: (col_name, col_idx)}, all_headers: [...], sheet_name: str}
        """
        import openpyxl

        if not os.path.exists(self.excel_path):
            return {"error": f"找不到文件: {self.excel_path}"}

        try:
            wb = openpyxl.load_workbook(self.excel_path, data_only=True)
        except Exception as e:
            return {"error": f"打开失败: {e}"}

        sheet_name = None
        for name in wb.sheetnames:
            if "测风" in name and "总表" in name:
                sheet_name = name
                break
        if not sheet_name:
            for name in wb.sheetnames:
                if "测风" in name or "塔" in name:
                    sheet_name = name
                    break
        if not sheet_name:
            wb.close()
            return {"error": f"找不到测风塔总表子表，可用: {wb.sheetnames}"}

        ws = wb[sheet_name]
        col_map, headers = self._build_column_map(ws)
        wb.close()

        matched = {}
        for field, idx in col_map.items():
            matched[field] = {"header": headers[idx], "col_index": idx}

        return {
            "sheet_name": sheet_name,
            "all_headers": headers,
            "matched": matched,
            "missing": [f for f in (REQUIRED_COLUMNS + OPTIONAL_COLUMNS) if f not in col_map],
        }
