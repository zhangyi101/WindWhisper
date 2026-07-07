"""
任务执行引擎
编排：完整性检查 → 按需下载 → 解密转换 → 输出报告
"""
import os
from datetime import datetime
from .config_loader import Config
from .integrity_checker import IntegrityChecker
from .email_fetcher import EmailFetcher
from .converter import RldConverter


class TaskExecutor:
    """任务执行器，协调所有模块完成一次完整的数据任务"""

    def __init__(self, config=None, progress_callback=None, log_callback=None):
        self.config = config or Config()
        self.checker = IntegrityChecker()
        self.fetcher = None
        self.converter = RldConverter(self.config.sympro_path)
        self.progress = progress_callback
        self.log = log_callback

    def _log(self, msg):
        if self.log:
            self.log(msg)

    def _progress(self, value, maximum=100):
        if self.progress:
            self.progress(value, maximum)

    def run(self, tower_list, date_from, date_to, skip_download=False, skip_convert=False):
        """
        执行完整任务流程
        """
        report = {
            "time_range": f"{date_from.date()} ~ {date_to.date()}",
            "projects": list(set(t["project"] for t in tower_list)),
            "towers": {},
            "download_summary": {"downloaded": 0, "skipped": 0},
            "convert_summary": {"converted": 0, "skipped": 0, "failed": 0},
        }

        try:
            self._run_internal(tower_list, date_from, date_to, skip_download, skip_convert, report)
        except Exception as e:
            err_msg = f"❌ 任务执行出错: {e}"
            print(err_msg)
            self._log(err_msg)
            import traceback
            tb = traceback.format_exc()
            print(tb)
            self._log(tb)
        finally:
            self._progress(100, 100)

        return report

    def _run_internal(self, tower_list, date_from, date_to, skip_download, skip_convert, report):

        total_towers = len(tower_list)
        self._log(f"开始执行任务：{report['time_range']}")
        self._log(f"涉及塔数：{total_towers}")

        # Step 1: 检查数据完整性
        self._log("阶段1：检查本地数据完整性...")
        self._progress(5, 100)
        check_results = self.checker.check_towers(
            tower_list, self.config.data_root, date_from, date_to
        )

        # 判断哪些塔需要下载
        towers_need_download = []
        towers_ready = []
        for t in tower_list:
            sc = t["short_code"]
            cr = check_results.get(sc, {})
            existing = cr.get("existing", 0)
            expected = cr.get("expected", 0)
            first = cr.get("first_date", "?")
            last = cr.get("last_date", "?")
            if cr.get("is_complete", False):
                towers_ready.append(t)
                self._log(f"  ✅ {sc}：{existing} 个文件 ({first} ~ {last})，完整")
            else:
                towers_need_download.append(t)
                missing = len(cr.get("missing_dates", []))
                self._log(f"  ⚠ {sc}：{existing} 个文件 ({first} ~ {last})，缺 {missing}/{expected} 天")

        report["check_results"] = check_results

        # Step 2: 按需下载
        if towers_need_download and not skip_download:
            self._log(f"\n阶段2：登录邮箱，下载缺失数据...")
            self._progress(10, 100)

            self.fetcher = EmailFetcher(self.config.mail_account, self.config.mail_auth)
            ok, msg = self.fetcher.login()
            if not ok:
                self._log(f"  ❌ 邮箱登录失败: {msg}")
                self._log("  请检查 config.json 中的授权码")
                self.fetcher = None
            else:
                self._log(f"  ✅ 邮箱登录成功")
                self._progress(20, 100)

                # 搜索邮件
                msg_numbers = self.fetcher.filter_by_date(date_from, date_to)
                self._log(f"  找到 {len(msg_numbers)} 封邮件")

                if msg_numbers:
                    self._progress(40, 100)

                    # 构建 tower_map（只包含当前塔列表）
                    tower_map = {}
                    for t in tower_list:
                        tower_map[t["full_code"]] = {
                            "short_code": t["short_code"],
                            "project": t["project"],
                        }

                    downloaded, skipped = self.fetcher.download_attachments(
                        msg_numbers, tower_map, self.config.data_root
                    )

                    total_dl = sum(
                        len(files.get("new", [])) for files in downloaded.values()
                    )
                    total_skip = sum(
                        len(files.get("skipped", [])) for files in downloaded.values()
                    )
                    self._log(f"  下载完成: 新增 {total_dl} 个，跳过 {total_skip} 个（已存在）")
                    for sc, files in downloaded.items():
                        n = len(files.get("new", []))
                        s = len(files.get("skipped", []))
                        if n > 0:
                            self._log(f"    {sc}: 新增 {n} 个，跳过 {s} 个")
                            report["towers"].setdefault(sc, {})["downloaded"] = n

                    if skipped:
                        self._log(f"  未匹配附件: {len(skipped)} 个")
                        report["download_summary"]["skipped"] = len(skipped)

                    report["download_summary"]["downloaded"] = total_dl
                    if self.fetcher:
                        self.fetcher.logout()

                self._progress(60, 100)
        elif skip_download:
            self._log("  跳过邮箱下载")
        else:
            self._log("  所有塔数据完整，无需下载")

        # Step 3: 解密转换
        if not skip_convert:
            self._log(f"\n阶段3：解密转换 .rld → .txt")
            self._progress(70, 100)

            ready, msg = self.converter.is_ready()
            if not ready:
                self._log(f"  ⚠ {msg}，跳过转换")
            else:
                # 对每个塔单独转换（使用各自的密码）
                total_conv = 0
                total_skip = 0
                for t in tower_list:
                    tower_dir = os.path.join(self.config.data_root, t["short_code"])
                    if not os.path.isdir(tower_dir):
                        continue

                    pwd = t.get("decrypt_pwd", "")
                    if not pwd:
                        self._log(f"  ⚠ {t['short_code']}：无解析密码，跳过转换")
                        continue

                    result = self.converter.convert_and_merge(
                        tower_dir, t["full_code"], pwd,
                        date_from=date_from, date_to=date_to
                    )
                    total_conv += result["converted"]
                    total_skip += result["skipped"]
                    if result.get("combined_txt"):
                        self._log(f"  ✅ {t['short_code']}：→ {os.path.basename(result['combined_txt'])}")
                    if result["failed"] > 0:
                        self._log(f"  ❌ {t['short_code']}：失败 {result['failed']} 个")
                    report["towers"].setdefault(t["short_code"], {})["converted"] = result["converted"]

                report["convert_summary"]["converted"] = total_conv
                report["convert_summary"]["skipped"] = total_skip
                self._progress(90, 100)
        else:
            self._log("  跳过解密转换")

        # 完成
        self._progress(100, 100)
        self._log("\n✅ 任务完成！")
        self._log(f"   下载: {report['download_summary']['downloaded']} 个")
        self._log(f"   转换: {report['convert_summary']['converted']} 个")

        return report

    def validate_local_only(self, tower_list, date_from, date_to):
        """
        仅验证本地数据完整性，不下载不转换
        用于界面"检测完整性"按钮
        """
        return self.checker.check_towers(
            tower_list, self.config.data_root, date_from, date_to
        )
