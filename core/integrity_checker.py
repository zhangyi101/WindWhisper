"""
数据完整性检查模块
扫描本地目录，判断指定时间段的数据是否齐全
不依赖任何第三方库（只用标准库）
"""
import os
import re
from datetime import datetime, timedelta, date


class IntegrityChecker:
    """检查测风塔本地数据是否完整"""

    def check_tower(self, tower_dir, short_code, date_from, date_to):
        """
        检查单个塔的数据完整性

        参数:
            tower_dir: 塔数据目录路径
            short_code: 塔短号（如 "7331"）
            date_from: datetime 或 date
            date_to: datetime 或 date

        返回: dict
            {
                "short_code": "7331",
                "is_complete": True/False,
                "expected": 30,
                "existing": 28,
                "missing_dates": ["2026-06-05", ...],
                "file_list": ["007331_2026-06-01...rld", ...]
            }
        """
        result = {
            "short_code": short_code,
            "is_complete": False,
            "expected": 0,
            "existing": 0,
            "first_date": None,
            "last_date": None,
            "missing_dates": [],
            "file_list": [],
        }

        if not os.path.isdir(tower_dir):
            return result

        # 生成预期日期集合
        d_from = date_from.date() if isinstance(date_from, datetime) else date_from
        d_to = date_to.date() if isinstance(date_to, datetime) else date_to
        expected = set()
        d = d_from
        while d <= d_to:
            expected.add(d)
            d += timedelta(days=1)

        result["expected"] = len(expected)

        # 扫描目录下所有 .rld 文件
        rld_files = []
        for fname in os.listdir(tower_dir):
            if fname.lower().endswith(".rld"):
                # 尝试从文件名中提取日期： YYYY-MM-DD
                match = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
                if match:
                    try:
                        file_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                        if d_from <= file_date <= d_to:
                            rld_files.append((file_date, fname))
                    except ValueError:
                        continue

        # 去重（同一天可能有多个文件，取最新）
        date_to_file = {}
        for fd, fn in sorted(rld_files, key=lambda x: x[0]):
            date_to_file[fd] = fn

        result["existing"] = len(date_to_file)
        result["file_list"] = list(date_to_file.values())

        # 记录实际覆盖的日期范围
        if date_to_file:
            sorted_dates = sorted(date_to_file.keys())
            result["first_date"] = str(sorted_dates[0])
            result["last_date"] = str(sorted_dates[-1])

        # 检查缺失
        existing_dates = set(date_to_file.keys())
        missing = sorted(expected - existing_dates)
        result["missing_dates"] = [str(m) for m in missing]
        result["is_complete"] = len(missing) == 0

        return result

    def check_towers(self, tower_list, data_root, date_from, date_to):
        """
        批量检查多个塔

        参数:
            tower_list: Config.get_tower_list() 返回的列表
            data_root: 数据根目录
            date_from, date_to: datetime 或 date

        返回: dict {short_code: check_tower() 的结果}
        """
        results = {}
        for t in tower_list:
            tower_dir = os.path.join(data_root, t["short_code"])
            result = self.check_tower(tower_dir, t["short_code"], date_from, date_to)
            result["project"] = t["project"]
            result["full_code"] = t["full_code"]
            result["decrypt_pwd"] = t["decrypt_pwd"]
            results[t["short_code"]] = result
        return results
