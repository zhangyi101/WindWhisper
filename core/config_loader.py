"""
配置加载模块
读取 config.json（用户配置）+ Excel 表格（塔信息）
所有配置集中管理，其他模块通过此模块获取配置
"""
import json
import os
import sys
from datetime import datetime


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
        """如果 config.json 不存在，创建默认模板"""
        default = {
            "邮箱": {
                "账号": "ATSC_01@163.com",
                "授权码": "请在这里填写网易邮箱授权码"
            },
            "路径": {
                "测风塔信息表": "C:\\Users\\Lenovo\\Desktop\\阳光新能源华南分公司测风简报-2025年12月.xlsx",
                "数据存储目录": "D:\\测风数据文件"
            },
            "解密": {
                "SymphoniePRO路径": "C:\\Program Files (x86)\\Renewable NRG Systems\\SymPRO Desktop\\SymPRODesktop.exe"
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

    def get_tower_list(self, projects=None):
        """
        从 Excel 读取华南测风塔总表，返回有效塔列表

        返回: list[dict]
            {
                "full_code": "007331",
                "short_code": "7331",
                "project": "禄劝九龙",
                "start_date": datetime 或 None,
                "note": "",
                "decrypt_pwd": "6655"
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

        # 自动查找"华南测风塔总表"子表
        sheet_name = None
        for name in wb.sheetnames:
            if "华南" in name and "总表" in name:
                sheet_name = name
                break
        if not sheet_name:
            print(f"找不到'华南测风塔总表'子表，可用: {wb.sheetnames}")
            wb.close()
            return []

        ws = wb[sheet_name]
        towers = []

        for row in ws.iter_rows(min_row=2, values_only=True):
            # 列索引（0-based）
            # A(0)=编号, B(1)=项目, J(9)=测风起始时间,
            # N(13)=备注, O(14)=数据解析密码, Q(16)=塔号
            code_raw = row[0]
            if code_raw is None:
                continue

            project = str(row[1]).strip() if row[1] else ""
            start_serial = row[9] if len(row) > 9 else None
            short_raw = row[16] if len(row) > 16 else None
            note = str(row[13]).strip() if len(row) > 13 and row[13] else ""
            decrypt_pwd = str(row[14]).strip() if len(row) > 14 and row[14] else ""

            # 过滤未立
            if "未立" in str(code_raw):
                continue

            # 统一编号为6位补零
            full_code = self._pad_code(code_raw)

            # 过滤起始时间为空的
            start_date = self._excel_date(start_serial)
            if start_date is None:
                continue

            # 短号
            if short_raw is not None:
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

    def _pad_code(self, code):
        """编号统一补零为6位"""
        if code is None:
            return None
        if isinstance(code, (int, float)):
            return f"{int(code):06d}"
        s = str(code).strip()
        if s.isdigit():
            return f"{int(s):06d}"
        return s

    def _excel_date(self, serial):
        """Excel日期序列号 → datetime"""
        if serial is None:
            return None
        try:
            from datetime import timedelta
            base = datetime(1899, 12, 30)
            return base + timedelta(days=int(serial))
        except (ValueError, TypeError):
            return None
