"""
邮箱下载模块
POP3 登录网易邮箱，按时间筛选，下载附件
铁律：只读不删不改
"""
import os
import time
import poplib
import ssl
import socket
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta

# 超时设置（秒）
POP3_TIMEOUT = 30
SOCKET_TIMEOUT = 15
SCAN_MAX_SECONDS = 1800  # 扫描最多30分钟（一年数据约需15-20分钟）


def decode_str(s):
    """解码邮件头"""
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            if charset:
                try:
                    result.append(part.decode(charset, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    result.append(part.decode("utf-8", errors="replace"))
            else:
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return "".join(result)


class EmailFetcher:
    """邮箱附件下载器"""

    def __init__(self, account, auth_code, server="pop.163.com", port=995):
        self.account = account
        self.auth_code = auth_code
        self.server = server
        self.port = port
        self.conn = None

    def login(self):
        """登录邮箱"""
        socket.setdefaulttimeout(SOCKET_TIMEOUT)
        ctx = ssl.create_default_context()
        self.conn = poplib.POP3_SSL(self.server, self.port, context=ctx, timeout=POP3_TIMEOUT)
        try:
            self.conn.user(self.account)
            self.conn.pass_(self.auth_code)
            num = len(self.conn.list()[1])
            return True, num
        except poplib.error_proto as e:
            self.conn = None
            return False, str(e)
        except socket.timeout:
            self.conn = None
            return False, "连接超时，请检查网络"

    def logout(self):
        """退出登录"""
        if self.conn:
            try:
                self.conn.quit()
            except Exception:
                pass
            self.conn = None

    def filter_by_date(self, date_from, date_to, progress_callback=None):
        """
        扫描邮件头，筛选指定日期范围内的邮件编号
        从最新邮件开始扫描，遇到比目标更早的邮件即停止
        兜底：到最旧邮件自动停（防止日期超出邮箱范围时死循环）
        """
        if not self.conn:
            return []

        num_messages = len(self.conn.list()[1])
        target_from = date_from.date()
        target_to = date_to.date()

        matched = []
        scan_count = 0
        start_time = time.time()

        for msg_num in range(num_messages, 0, -1):
            scan_count += 1

            # 总时间限制：超过30分钟强制停止
            if time.time() - start_time > SCAN_MAX_SECONDS:
                break

            if progress_callback and scan_count % 50 == 0:
                progress_callback(scan_count, num_messages, len(matched))

            # 已到最旧邮件
            if msg_num <= 1:
                break

            try:
                headers = self.conn.top(msg_num, 0)[1]
                header_text = b"\r\n".join(headers).decode("utf-8", errors="replace")

                msg_date = None
                for line in header_text.split("\r\n"):
                    if line.lower().startswith("date:"):
                        parsed = parsedate_to_datetime(line[5:].strip())
                        if parsed:
                            msg_date = parsed.date()
                        break

                if msg_date is None:
                    continue
                if target_from <= msg_date <= target_to:
                    matched.append(msg_num)
                elif msg_date < target_from:
                    break  # 已超出目标范围，停止

            except Exception:
                continue

        elapsed = time.time() - start_time
        if elapsed > SCAN_MAX_SECONDS:
            print(f"扫描超时（{elapsed:.0f}秒），已停止")

        return matched

    def download_attachments(self, msg_numbers, tower_map, data_root, progress_callback=None):
        """
        下载指定邮件的附件，按塔号归档

        参数:
            msg_numbers: 邮件编号列表
            tower_map: dict {6位全号: {"short_code":短号, ...}}
            data_root: 数据根目录

        返回: (downloaded_dict, skipped_list)
            downloaded: {short_code: [文件名列表]}
            skipped: [(文件名, 主题), ...]
        """
        if not self.conn:
            return {}, []

        downloaded = {}
        skipped = []
        total = len(msg_numbers)

        for idx, msg_num in enumerate(sorted(msg_numbers)):
            try:
                resp = self.conn.retr(msg_num)
                raw = b"\r\n".join(resp[1])
                message = email.message_from_bytes(raw)
            except Exception:
                continue

            subject = decode_str(message["Subject"])

            for part in message.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get("Content-Disposition") is None:
                    continue
                if "attachment" not in str(part.get("Content-Disposition")).lower():
                    continue

                raw_name = part.get_filename()
                if raw_name is None:
                    continue

                fname = decode_str(raw_name)
                fname = self._safe_name(fname)
                if not fname:
                    continue

                # 匹配塔号
                matched_code = None
                for code in tower_map:
                    if fname.startswith(code + "_") or fname.startswith(code + "-"):
                        matched_code = code
                        break

                if matched_code is None:
                    skipped.append((fname, subject))
                    continue

                info = tower_map[matched_code]
                short_code = info["short_code"]
                target_dir = os.path.join(data_root, short_code)
                os.makedirs(target_dir, exist_ok=True)
                target_path = os.path.join(target_dir, fname)

                # 已存在则跳过
                if os.path.exists(target_path):
                    if short_code not in downloaded:
                        downloaded[short_code] = {"new": [], "skipped": []}
                    downloaded[short_code]["skipped"].append(fname)
                    continue

                try:
                    with open(target_path, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    if short_code not in downloaded:
                        downloaded[short_code] = {"new": [], "skipped": []}
                    downloaded[short_code]["new"].append(fname)
                except Exception as e:
                    print(f"下载失败 {filename}: {e}")
                    continue
            if progress_callback and (idx + 1) % 10 == 0:
                progress_callback(idx + 1, total)

        return downloaded, skipped

    def _safe_name(self, fname):
        """清理文件名中的非法字符"""
        if fname is None:
            return None
        import re
        fname = os.path.basename(fname)
        return re.sub(r'[<>:"/\\|?*]', "_", fname)
