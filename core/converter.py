"""
解密转换模块
调用 nrgpy / SymphoniePRO Desktop 将 .rld 解密为 .txt
增量逻辑：已有 _meas.txt 的跳过
输出策略：nrgpy → 临时目录 → 合并筛选 → TXT输出/ 子目录（不污染.rld文件夹）
"""
import os
import re
import shutil


class RldConverter:
    """RLD 文件解密转换器"""

    def __init__(self, sympro_path=None):
        self.sympro_path = sympro_path
        self.nrgpy_available = False
        self._check_nrgpy()

    def _check_nrgpy(self):
        try:
            import nrgpy
            self.nrgpy_available = True
        except ImportError:
            self.nrgpy_available = False

    def is_ready(self):
        if not self.nrgpy_available:
            return False, "nrgpy 未安装"
        if self.sympro_path and not os.path.exists(self.sympro_path):
            return False, f"SymphoniePRO 未找到: {self.sympro_path}"
        return True, "就绪"

    def convert_and_merge(self, tower_dir, full_code, decrypt_pwd,
                          date_from=None, date_to=None, convert_type="meas"):
        """
        转换 + 合并 + 筛选日期范围 → 输出到 TXT输出 子目录

        参数:
            tower_dir: 塔数据目录（存放.rld的地方）
            full_code: 6位补零编号
            decrypt_pwd: 解密密码
            date_from, date_to: datetime（可选，用于筛选数据行）
            convert_type: "meas"

        返回: dict {converted, skipped, failed, combined_txt}
        """
        result = {"converted": 0, "skipped": 0, "failed": 0, "combined_txt": None}

        if not os.path.isdir(tower_dir):
            return result
        if not self.nrgpy_available:
            return result

        import nrgpy

        # 临时目录（在塔目录外，用完删掉）
        temp_dir = os.path.join(tower_dir, "_temp_convert")
        out_dir = os.path.join(tower_dir, "TXT输出")
        os.makedirs(out_dir, exist_ok=True)

        # 扫描 .rld 文件
        rld_files = sorted([f for f in os.listdir(tower_dir) if f.endswith(".rld")])
        to_convert = []

        for rf in rld_files:
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", rf)
            if not date_match:
                continue
            # 如果日期在范围内，并且输出目录里还没有合并文件，则需要转换
            to_convert.append(rf)

        if not to_convert:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return result

        # 清理旧临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        # 用 nrgpy 转换所有 .rld → _meas.txt（输出到临时目录）
        try:
            converter = nrgpy.local_rld(
                rld_dir=tower_dir,
                out_dir=temp_dir,
                encryption_pass=decrypt_pwd,
                file_filter=full_code,
                sympro_path=self.sympro_path,
            )
            converter.directory()

            # 统计
            for rf in to_convert:
                base = os.path.splitext(rf)[0]
                expected = os.path.join(temp_dir, f"{base}_{convert_type}.txt")
                if os.path.exists(expected):
                    result["converted"] += 1
                else:
                    result["failed"] += 1

        except Exception as e:
            result["failed"] = len(to_convert)
            print(f"nrgpy 转换失败: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return result

        # 合并临时目录里的所有 _meas.txt → 筛选日期范围 → 输出到 TXT输出/
        if result["converted"] > 0:
            combined = self._merge_and_filter(
                temp_dir, out_dir, full_code, date_from, date_to, convert_type
            )
            result["combined_txt"] = combined

        # 清理临时目录（不留痕迹）
        shutil.rmtree(temp_dir, ignore_errors=True)

        return result

    def _merge_and_filter(self, temp_dir, out_dir, full_code, date_from, date_to, convert_type):
        """合并临时目录的所有 _meas.txt，筛选日期，输出到 out_dir"""
        import re

        txt_info = []
        for f in os.listdir(temp_dir):
            if f.endswith(f"_{convert_type}.txt") and f.startswith(full_code):
                match = re.search(r"(\d{4}-\d{2}-\d{2})", f)
                if match:
                    txt_info.append((match.group(1), f))

        if not txt_info:
            return None

        txt_info.sort()
        txt_files = [x[1] for x in txt_info]

        # 提前转换日期范围（下面判断文件名要用）
        target_from = date_from.date() if hasattr(date_from, 'date') else date_from if date_from else None
        target_to = date_to.date() if hasattr(date_to, 'date') else date_to if date_to else None

        # 文件名中的日期范围 = 用户选择的筛选范围（而非全部文件范围）
        if target_from and target_to:
            first_date = str(target_from)
            last_date = str(target_to)
        else:
            first_date = txt_info[0][0]
            last_date = txt_info[-1][0]

        combined_name = f"{full_code}_{first_date}_{last_date}_combined.txt"
        combined_path = os.path.join(out_dir, combined_name)

        with open(combined_path, "w", encoding="utf-8") as out:
            for i, fname in enumerate(txt_files):
                fpath = os.path.join(temp_dir, fname)
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                lines = content.split("\n")

                if i == 0:
                    # 第一个文件：写入头部信息 + 筛选后的数据行
                    header_end = 0
                    for j, line in enumerate(lines):
                        if line.startswith("Timestamp"):
                            header_end = j
                            break
                    # 写头部段
                    for j in range(header_end + 1):
                        out.write(lines[j] + "\n")
                    # 写筛选后的数据行
                    for j in range(header_end + 1, len(lines)):
                        if not lines[j].strip():
                            continue
                        if self._in_range(lines[j], target_from, target_to):
                            out.write(lines[j] + "\n")
                else:
                    # 后续文件：只写数据行（跳过头部）
                    data_start = None
                    for j, line in enumerate(lines):
                        if line.startswith("Timestamp"):
                            data_start = j + 1
                            break
                    if data_start:
                        for j in range(data_start, len(lines)):
                            if not lines[j].strip():
                                continue
                            if self._in_range(lines[j], target_from, target_to):
                                out.write(lines[j] + "\n")

        return combined_path

    def _in_range(self, line, target_from, target_to):
        """检查数据行的时间戳是否在范围内"""
        if target_from is None and target_to is None:
            return True
        try:
            ts_str = line.split("\t")[0]
            from datetime import datetime
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if target_from and ts.date() < target_from:
                return False
            if target_to and ts.date() > target_to:
                return False
            return True
        except Exception:
            return True  # 解析失败的行保留

    def convert_towers(self, tower_infos, data_root, date_from=None, date_to=None):
        """批量转换多个塔"""
        results = {}
        for info in tower_infos:
            tower_dir = os.path.join(data_root, info["short_code"])
            result = self.convert_and_merge(
                tower_dir, info["full_code"], info["decrypt_pwd"],
                date_from, date_to
            )
            results[info["short_code"]] = result
        return results
