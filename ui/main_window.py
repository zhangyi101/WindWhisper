"""
风语 v2.0 — 主窗口
包含：数据任务、配置、定时任务、日志 四个标签页

v2.0 改进：
- 文件菜单：打开数据目录/塔文件夹/重新加载塔信息表
- 设置菜单：字体大小/图标大小/角色头像大小调节
- TaskPanel：刷新塔列表按钮
- 修复：_test_now 实现、filename 变量 bug、日志输出改善
"""
import os
import sys
import json
import subprocess
from datetime import datetime, date, timedelta

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QLabel, QDateEdit, QGroupBox, QGridLayout, QTextEdit,
    QFileDialog, QMessageBox, QProgressBar, QSplitter, QFrame,
    QLineEdit, QScrollArea, QSizePolicy, QComboBox, QSpinBox,
    QSlider, QAction
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QTimer, QPoint, QSize
from PyQt5.QtGui import QFont, QIcon, QColor, QPixmap

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LogSignal(QTextEdit):
    """日志输出控件，支持颜色标记"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 8px;
            }
        """)

    def append_log(self, msg, level="info"):
        colors = {"info": "#d4d4d4", "ok": "#4ec9b0", "warn": "#dcdcaa", "error": "#f44747"}
        color = colors.get(level, "#d4d4d4")
        icon = {"info": "•", "ok": "✅", "warn": "⚠", "error": "❌"}.get(level, "•")
        html = f'<span style="color:{color}">{icon} {msg}</span><br>'
        self.insertHtml(html)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        QApplication.processEvents()


class TaskWorker(QThread):
    """后台任务线程，避免界面卡死"""
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str, str)
    finished = pyqtSignal(dict)

    def __init__(self, executor, tower_list, date_from, date_to, skip_download, skip_convert):
        super().__init__()
        self.executor = executor
        self.tower_list = tower_list
        self.date_from = date_from
        self.date_to = date_to
        self.skip_download = skip_download
        self.skip_convert = skip_convert

    def run(self):
        try:
            self.executor.progress = lambda v, m: self.progress.emit(v, m)
            self.executor.log = lambda msg, level="info": self.log.emit(msg, level)
            result = self.executor.run(
                self.tower_list, self.date_from, self.date_to,
                self.skip_download, self.skip_convert
            )
            self.finished.emit(result)
        except Exception as e:
            import traceback
            self.log.emit(f"任务异常: {e}", "error")
            self.log.emit(traceback.format_exc(), "error")
            self.finished.emit({"error": str(e)})


class TaskPanel(QWidget):
    """数据任务面板"""
    def __init__(self, config, executor, log_widget, main_window=None):
        super().__init__()
        self.config = config
        self.executor = executor
        self.log_widget = log_widget
        self.main_window = main_window
        self.all_towers = []
        self.selected_towers = []
        self._setup_ui()
        self._load_towers()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 项目选择区
        proj_group = QGroupBox("选择项目")
        proj_layout = QVBoxLayout(proj_group)

        # 刷新按钮行
        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新塔列表")
        refresh_btn.setToolTip("重新读取 Excel 表格，更新塔列表")
        refresh_btn.clicked.connect(self._refresh_towers)
        refresh_layout.addWidget(refresh_btn)
        refresh_layout.addStretch()

        # 显示当前 Excel 路径
        self.excel_label = QLabel()
        self.excel_label.setStyleSheet("color: #888; font-size: 11px;")
        refresh_layout.addWidget(self.excel_label)
        proj_layout.addLayout(refresh_layout)

        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["项目 / 测风塔", "编号", "密码", "状态"])
        self.project_tree.setColumnWidth(0, 250)
        self.project_tree.setColumnWidth(1, 100)
        self.project_tree.setColumnWidth(2, 80)
        self.project_tree.setIndentation(20)
        self.project_tree.itemChanged.connect(self._on_item_changed)
        proj_layout.addWidget(self.project_tree)

        # 全选复选框
        sel_layout = QHBoxLayout()
        self.select_all_cb = QCheckBox("全选")
        self.select_all_cb.setChecked(True)
        self.select_all_cb.stateChanged.connect(self._on_select_all_toggle)
        sel_layout.addWidget(self.select_all_cb)
        sel_layout.addStretch()
        proj_layout.addLayout(sel_layout)

        layout.addWidget(proj_group)

        # 时间选择区
        time_group = QGroupBox("时间范围")
        time_layout = QGridLayout(time_group)

        time_layout.addWidget(QLabel("从:"), 0, 0)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        time_layout.addWidget(self.date_from, 0, 1)

        time_layout.addWidget(QLabel("至:"), 0, 2)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate().addDays(-1))
        time_layout.addWidget(self.date_to, 0, 3)

        # 快捷按钮
        btn_layout = QHBoxLayout()
        for text, months in [("上月", -1), ("本月", 0), ("本季度", -3), ("全年", -12)]:
            btn = QPushButton(text)
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda checked, m=months: self._quick_date(m))
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        time_layout.addLayout(btn_layout, 1, 0, 1, 4)
        layout.addWidget(time_group)

        # 操作按钮
        action_layout = QHBoxLayout()

        self.check_btn = QPushButton("🔍 检测完整性")
        self.check_btn.clicked.connect(self._check_integrity)
        action_layout.addWidget(self.check_btn)

        self.execute_btn = QPushButton("▶ 执行任务")
        self.execute_btn.setStyleSheet("""
            QPushButton { background-color: #0e639c; color: white; font-weight: bold;
                          padding: 8px 24px; border-radius: 4px; font-size: 14px; }
            QPushButton:hover { background-color: #1177bb; }
            QPushButton:disabled { background-color: #555; }
        """)
        self.execute_btn.clicked.connect(self._execute)
        self.execute_btn.setEnabled(False)
        action_layout.addWidget(self.execute_btn)

        self.skip_dl_cb = QCheckBox("跳过下载")
        self.skip_conv_cb = QCheckBox("跳过转换")
        action_layout.addWidget(self.skip_dl_cb)
        action_layout.addWidget(self.skip_conv_cb)

        layout.addLayout(action_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def _refresh_towers(self):
        """重新读取 Excel，刷新塔列表"""
        self.log_widget.append_log("正在重新读取测风塔信息表...", "info")
        # 重新加载 config（以防 Excel 路径变了）
        if self.main_window:
            self.main_window._reload_config()
        self._load_towers()

    def _load_towers(self):
        """从 Excel 加载塔列表到树"""
        self.project_tree.blockSignals(True)
        self.project_tree.clear()

        # 更新 Excel 路径显示
        excel_name = os.path.basename(self.config.excel_path) if self.config.excel_path else "(未配置)"
        self.excel_label.setText(f"当前表格: {excel_name}")

        self.all_towers = self.config.get_tower_list()

        if not self.all_towers:
            self.log_widget.append_log("⚠ 未读取到任何塔信息，请检查 Excel 表格", "warn")
            # 显示映射信息帮助排查
            info = self.config.get_column_mapping_info()
            if "error" in info:
                self.log_widget.append_log(f"  错误: {info['error']}", "error")
            else:
                self.log_widget.append_log(f"  匹配到的列: {info.get('matched', {})}", "info")
                self.log_widget.append_log(f"  缺失的列: {info.get('missing', [])}", "warn")
        else:
            self.log_widget.append_log(f"✅ 读取到 {len(self.all_towers)} 个测风塔", "ok")

        # 按项目分组
        projects = {}
        for t in self.all_towers:
            proj = t["project"]
            if proj not in projects:
                projects[proj] = []
            projects[proj].append(t)

        for proj_name in sorted(projects.keys()):
            proj_item = QTreeWidgetItem([proj_name, "", "", ""])
            proj_item.setFlags(proj_item.flags() | Qt.ItemIsUserCheckable)
            proj_item.setCheckState(0, Qt.Checked)
            proj_item.setData(0, Qt.UserRole, "project")

            for t in projects[proj_name]:
                pwd_display = t.get("decrypt_pwd", "") or "—"
                tower_item = QTreeWidgetItem([
                    f"  塔 {t['short_code']}",
                    t["full_code"],
                    pwd_display,
                    ""
                ])
                tower_item.setFlags(tower_item.flags() | Qt.ItemIsUserCheckable)
                tower_item.setCheckState(0, Qt.Checked)
                tower_item.setData(0, Qt.UserRole, "tower")
                tower_item.setData(1, Qt.UserRole, t)
                proj_item.addChild(tower_item)

            self.project_tree.addTopLevelItem(proj_item)
            proj_item.setExpanded(True)

        self.project_tree.blockSignals(False)
        self._update_selection()
        self.check_btn.setEnabled(len(self.selected_towers) > 0)

    def _on_item_changed(self, item, column):
        """勾选状态变化时同步更新"""
        if column != 0:
            return
        role = item.data(0, Qt.UserRole)
        if role == "project":
            checked = item.checkState(0) == Qt.Checked
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
        self._update_selection()
        self.check_btn.setEnabled(len(self.selected_towers) > 0)

    def _on_select_all_toggle(self, state):
        """全选复选框：勾选=全选，不勾选=全不选。不影响后续手选"""
        self.project_tree.blockSignals(True)
        checked = (state == Qt.Checked)
        for i in range(self.project_tree.topLevelItemCount()):
            proj = self.project_tree.topLevelItem(i)
            proj.setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
            for j in range(proj.childCount()):
                proj.child(j).setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
        self.project_tree.blockSignals(False)
        self._update_selection()
        if hasattr(self, 'check_btn'):
            self.check_btn.setEnabled(len(self.selected_towers) > 0)

    def _update_selection(self):
        """更新选中塔列表"""
        self.selected_towers = []
        for i in range(self.project_tree.topLevelItemCount()):
            proj = self.project_tree.topLevelItem(i)
            for j in range(proj.childCount()):
                child = proj.child(j)
                if child.checkState(0) == Qt.Checked:
                    t = child.data(1, Qt.UserRole)
                    if t:
                        self.selected_towers.append(t)

    def _quick_date(self, months_offset):
        """快捷日期选择"""
        today = QDate.currentDate()
        if months_offset < 0:
            first = today.addMonths(months_offset)
            first = QDate(first.year(), first.month(), 1)
            last = today.addDays(-1)
        elif months_offset == 0:
            first = QDate(today.year(), today.month(), 1)
            last = today
        else:
            first = today.addMonths(months_offset)
            first = QDate(first.year(), first.month(), 1)
            last = today.addDays(-1)

        self.date_from.setDate(first)
        self.date_to.setDate(last)

    def _check_integrity(self):
        """检测所选塔的数据完整性"""
        if not self.selected_towers:
            QMessageBox.warning(self, "提示", "请先选择测风塔")
            return

        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()
        d_from_dt = datetime.combine(d_from, datetime.min.time())
        d_to_dt = datetime.combine(d_to, datetime.min.time())

        self.log_widget.append_log(f"检测完整性: {d_from} ~ {d_to}", "info")

        results = self.executor.validate_local_only(
            self.selected_towers, d_from_dt, d_to_dt
        )
        all_complete = True
        for sc, r in results.items():
            existing = r.get("existing", 0)
            expected = r.get("expected", 0)
            first = r.get("first_date", "?")
            last = r.get("last_date", "?")
            if r.get("is_complete"):
                self.log_widget.append_log(
                    f"  ✅ {sc}：{existing} 个文件 ({first} ~ {last})，完整", "ok")
            else:
                all_complete = False
                missing_count = len(r.get("missing_dates", []))
                self.log_widget.append_log(
                    f"  ⚠ {sc}：{existing} 个文件 ({first} ~ {last})，缺 {missing_count}/{expected} 天",
                    "warn")
                missing_list = r.get("missing_dates", [])
                if len(missing_list) <= 10:
                    for md in missing_list:
                        self.log_widget.append_log(f"    缺: {md}", "warn")

        # 更新树上的状态
        for i in range(self.project_tree.topLevelItemCount()):
            proj = self.project_tree.topLevelItem(i)
            for j in range(proj.childCount()):
                child = proj.child(j)
                t = child.data(1, Qt.UserRole)
                if t and t["short_code"] in results:
                    r = results[t["short_code"]]
                    if r.get("is_complete"):
                        child.setText(3, "✅ 完整")
                    else:
                        child.setText(3, f"⚠ 缺{len(r.get('missing_dates',[]))}天")

        if all_complete:
            self.log_widget.append_log("所有塔数据完整！可直接解密转换。", "ok")
        else:
            self.log_widget.append_log("部分塔数据缺失，执行时将自动下载。", "warn")

        self.execute_btn.setEnabled(len(self.selected_towers) > 0)

    def _execute(self):
        """执行任务"""
        if not self.selected_towers:
            QMessageBox.warning(self, "提示", "请先选择测风塔")
            return

        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()
        d_from_dt = datetime.combine(d_from, datetime.min.time())
        d_to_dt = datetime.combine(d_to, datetime.min.time())

        self.execute_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = TaskWorker(
            self.executor, self.selected_towers, d_from_dt, d_to_dt,
            self.skip_dl_cb.isChecked(), self.skip_conv_cb.isChecked()
        )
        self.worker.progress.connect(lambda v, m: self.progress_bar.setValue(int(v / m * 100)) if m > 0 else None)
        self.worker.log.connect(self.log_widget.append_log)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, report):
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)
        self.check_btn.setEnabled(True)

        if "error" in report:
            self.log_widget.append_log(f"❌ 任务执行异常: {report['error']}", "error")
            QMessageBox.critical(self, "执行失败", f"任务执行异常:\n{report['error']}")
            return

        self.log_widget.append_log("=" * 40, "info")
        self.log_widget.append_log(f"任务完成！时间范围: {report.get('time_range', '')}", "ok")
        self.log_widget.append_log(f"下载: {report.get('download_summary', {}).get('downloaded', 0)} 个", "info")
        self.log_widget.append_log(f"转换: {report.get('convert_summary', {}).get('converted', 0)} 个", "info")
        self.log_widget.append_log("=" * 40, "info")

    def get_selected_tower(self):
        """获取当前选中的单个塔（用于文件菜单"打开塔文件夹"）"""
        items = self.project_tree.selectedItems()
        if items:
            item = items[0]
            if item.data(0, Qt.UserRole) == "tower":
                return item.data(1, Qt.UserRole)
        return None


class ConfigPanel(QWidget):
    """配置面板"""
    def __init__(self, config, log_widget, main_window=None):
        super().__init__()
        self.config = config
        self.log_widget = log_widget
        self.main_window = main_window
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel("配置保存在 config.json 中，用记事本也能修改。")
        info.setStyleSheet("color: #888; padding: 4px;")
        layout.addWidget(info)

        form = QGridLayout()
        form.setSpacing(8)

        form.addWidget(QLabel("邮箱账号:"), 0, 0)
        self.mail_edit = QLineEdit(self.config.mail_account)
        form.addWidget(self.mail_edit, 0, 1)

        form.addWidget(QLabel("邮箱授权码:"), 1, 0)
        self.auth_edit = QLineEdit(self.config.mail_auth)
        self.auth_edit.setEchoMode(QLineEdit.Password)
        form.addWidget(self.auth_edit, 1, 1)
        self.show_auth_btn = QPushButton("👁")
        self.show_auth_btn.setFixedWidth(30)
        self.show_auth_btn.clicked.connect(
            lambda: self.auth_edit.setEchoMode(
                QLineEdit.Normal if self.auth_edit.echoMode() == QLineEdit.Password
                else QLineEdit.Password
            ))
        form.addWidget(self.show_auth_btn, 1, 2)

        form.addWidget(QLabel("Excel 表格路径:"), 2, 0)
        excel_layout = QHBoxLayout()
        self.excel_edit = QLineEdit(self.config.excel_path)
        excel_layout.addWidget(self.excel_edit)
        excel_btn = QPushButton("浏览...")
        excel_btn.clicked.connect(lambda: self._browse_file(self.excel_edit, "Excel 文件 (*.xlsx)"))
        excel_layout.addWidget(excel_btn)
        form.addLayout(excel_layout, 2, 1, 1, 2)

        form.addWidget(QLabel("数据存储目录:"), 3, 0)
        dir_layout = QHBoxLayout()
        self.dir_edit = QLineEdit(self.config.data_root)
        dir_layout.addWidget(self.dir_edit)
        dir_btn = QPushButton("浏览...")
        dir_btn.clicked.connect(lambda: self._browse_dir())
        dir_layout.addWidget(dir_btn)
        form.addLayout(dir_layout, 3, 1, 1, 2)

        form.addWidget(QLabel("SymphoniePRO 路径:"), 4, 0)
        sp_layout = QHBoxLayout()
        self.sp_edit = QLineEdit(self.config.sympro_path)
        sp_layout.addWidget(self.sp_edit)
        sp_btn = QPushButton("浏览...")
        sp_btn.clicked.connect(lambda: self._browse_file(self.sp_edit, "可执行文件 (*.exe)"))
        sp_layout.addWidget(sp_btn)
        form.addLayout(sp_layout, 4, 1, 1, 2)

        layout.addLayout(form)

        save_btn = QPushButton("💾 保存配置")
        save_btn.setStyleSheet("""
            QPushButton { background-color: #0e639c; color: white; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #1177bb; }
        """)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        layout.addStretch()

    def _browse_file(self, edit, filter_str):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", edit.text(), filter_str)
        if path:
            edit.setText(path)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择目录", self.dir_edit.text())
        if path:
            self.dir_edit.setText(path)

    def _save(self):
        self.config.mail_account = self.mail_edit.text().strip()
        self.config.mail_auth = self.auth_edit.text().strip()
        self.config.excel_path = self.excel_edit.text().strip()
        self.config.data_root = self.dir_edit.text().strip()
        self.config.sympro_path = self.sp_edit.text().strip()

        if self.config.save():
            self.log_widget.append_log("配置已保存", "ok")
            # 通知主窗口刷新塔列表
            if self.main_window:
                self.main_window._reload_config()
        else:
            self.log_widget.append_log("配置保存失败", "error")


class SchedulePanel(QWidget):
    """定时任务面板"""
    def __init__(self, config, executor, log_widget):
        super().__init__()
        self.config = config
        self.executor = executor
        self.log_widget = log_widget
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel("定时任务使用 Windows 任务计划程序执行。设置后软件会自动创建任务。")
        info.setStyleSheet("color: #888; padding: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QGridLayout()
        form.setSpacing(8)

        self.enable_cb = QCheckBox("启用定时任务")
        form.addWidget(self.enable_cb, 0, 0, 1, 2)

        form.addWidget(QLabel("执行日期:"), 1, 0)
        day_layout = QHBoxLayout()
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 28)
        self.day_spin.setValue(1)
        day_layout.addWidget(self.day_spin)
        day_layout.addWidget(QLabel("号"))
        form.addLayout(day_layout, 1, 1)

        form.addWidget(QLabel("执行时间:"), 2, 0)
        time_layout = QHBoxLayout()
        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setValue(8)
        time_layout.addWidget(self.hour_spin)
        time_layout.addWidget(QLabel(":"))
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 59)
        self.min_spin.setValue(0)
        time_layout.addWidget(self.min_spin)
        form.addLayout(time_layout, 2, 1)

        form.addWidget(QLabel("数据范围:"), 3, 0)
        self.range_combo = QComboBox()
        self.range_combo.addItems(["上个月整月", "上个月 + 本月至今", "当月整月"])
        form.addWidget(self.range_combo, 3, 1)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 保存定时任务")
        save_btn.setStyleSheet("""
            QPushButton { background-color: #0e639c; color: white; padding: 8px 16px; border-radius: 4px; }
            QPushButton:hover { background-color: #1177bb; }
        """)
        save_btn.clicked.connect(self._save_schedule)
        btn_layout.addWidget(save_btn)

        test_btn = QPushButton("▶ 立即测试")
        test_btn.clicked.connect(self._test_now)
        btn_layout.addWidget(test_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _save_schedule(self):
        """使用 Windows 任务计划程序创建定时任务"""
        try:
            import win32com.client
            scheduler = win32com.client.Dispatch("Schedule.Service")
            scheduler.Connect()
            root = scheduler.GetFolder("\\")

            # 删除旧任务
            try:
                root.DeleteTask("风哨定时任务", 0)
            except Exception:
                pass

            # 创建新任务
            task_def = scheduler.NewTask(0)
            task_def.RegistrationInfo.Description = "风哨 — 测风塔数据自动下载与转换"

            # 触发器
            trigger = task_def.Triggers.Create(2)  # TASK_TRIGGER_MONTHLY
            trigger.DaysOfMonth = self.day_spin.value()
            trigger.MonthsOfYear = 4095  # 所有月份
            trigger.StartBoundary = f"2026-01-01T{self.hour_spin.value():02d}:{self.min_spin.value():02d}:00"

            # 动作
            exe_path = sys.executable if not getattr(sys, 'frozen', False) else sys.executable
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "core", "executor.py")

            action = task_def.Actions.Create(0)  # TASK_ACTION_EXEC
            action.Path = exe_path
            action.Arguments = f'"{script_path}"'

            # 设置
            task_def.Settings.Enabled = True
            task_def.Settings.AllowDemandStart = True
            task_def.Settings.StartWhenAvailable = True

            root.RegisterTaskDefinition(
                "风哨定时任务", task_def,
                6,  # TASK_CREATE_OR_UPDATE
                None, None, 0
            )

            self.log_widget.append_log(
                f"定时任务已创建：每月{self.day_spin.value()}号 {self.hour_spin.value():02d}:{self.min_spin.value():02d}",
                "ok")

        except ImportError:
            self.log_widget.append_log("需要安装 pywin32 模块以支持定时任务", "error")
            self.log_widget.append_log("请在命令行运行: pip install pywin32", "info")
        except Exception as e:
            self.log_widget.append_log(f"创建定时任务失败: {e}", "error")

    def _test_now(self):
        """立即执行一次测试任务（上月数据，仅检测不下载）"""
        self.log_widget.append_log("定时任务测试：立即执行（仅检测完整性）...", "info")
        from core.integrity_checker import IntegrityChecker
        checker = IntegrityChecker()

        # 获取上月日期范围
        today = date.today()
        if today.month == 1:
            prev_month = date(today.year - 1, 12, 1)
        else:
            prev_month = date(today.year, today.month - 1, 1)
        d_from = datetime.combine(prev_month, datetime.min.time())
        d_to = datetime.combine(today.replace(day=1) - timedelta(days=1), datetime.min.time())

        towers = self.config.get_tower_list()
        if not towers:
            self.log_widget.append_log("  ⚠ 未读取到塔信息，请检查 Excel 表格", "warn")
            return

        results = checker.check_towers(towers, self.config.data_root, d_from, d_to)
        total_ok = 0
        total_missing = 0
        for sc, r in results.items():
            if r.get("is_complete"):
                total_ok += 1
                self.log_widget.append_log(f"  ✅ {sc}: {r['existing']}/{r['expected']} 完整", "ok")
            else:
                missing = len(r.get("missing_dates", []))
                total_missing += missing
                self.log_widget.append_log(f"  ⚠ {sc}: {r['existing']}/{r['expected']} 缺{missing}天", "warn")

        self.log_widget.append_log(
            f"测试完成: {total_ok}/{len(results)} 个塔完整，共缺 {total_missing} 天",
            "ok" if total_missing == 0 else "warn")


class MainWindow(QMainWindow):
    """风语主窗口 v2.0"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("风语 v2.0 — 测风塔数据自动化工具")
        self.setMinimumSize(900, 650)

        # 初始化核心
        from core.config_loader import Config
        from core.executor import TaskExecutor
        self.config = Config()
        self.executor = TaskExecutor(self.config)

        # 界面
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # ===== 菜单栏 =====
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        # 重新加载塔信息表
        reload_action = QAction("🔄 重新加载塔信息表", self)
        reload_action.setShortcut("F5")
        reload_action.setStatusTip("重新读取 Excel 表格，更新塔列表")
        reload_action.triggered.connect(self._reload_config)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        # 打开数据目录
        open_data_action = QAction("📂 打开数据目录", self)
        open_data_action.setStatusTip("在资源管理器中打开数据存储根目录")
        open_data_action.triggered.connect(self._open_data_dir)
        file_menu.addAction(open_data_action)

        # 打开选中塔的文件夹
        open_tower_action = QAction("📁 打开选中塔文件夹", self)
        open_tower_action.setStatusTip("在资源管理器中打开当前选中塔的数据目录")
        open_tower_action.triggered.connect(self._open_tower_dir)
        file_menu.addAction(open_tower_action)

        # 打开 TXT 输出目录
        open_txt_action = QAction("📄 打开 TXT 输出目录", self)
        open_txt_action.setStatusTip("在资源管理器中打开选中塔的解密输出目录")
        open_txt_action.triggered.connect(self._open_txt_dir)
        file_menu.addAction(open_txt_action)

        file_menu.addSeparator()

        # 打开 Excel 表格
        open_excel_action = QAction("📊 打开测风塔信息表", self)
        open_excel_action.setStatusTip("用默认程序打开 Excel 表格")
        open_excel_action.triggered.connect(self._open_excel)
        file_menu.addAction(open_excel_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 设置菜单
        settings_menu = menubar.addMenu("设置(&S)")

        # 主题子菜单
        theme_menu = settings_menu.addMenu("主题风格")
        themes = [
            ("念头通达", "fanren_xiuxian"),
            ("暗夜科技", "dark_tech"),
            ("浅紫天蓝", "ocean_blue"),
            ("极简亮色", "clean_light"),
            ("枫叶银杏", "lingcage"),
        ]
        for label, key in themes:
            action = theme_menu.addAction(label)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self._load_theme(k))

        # 显示设置子菜单
        display_menu = settings_menu.addMenu("显示设置")

        # 字体大小
        display_menu.addAction(QAction("字体大小...", self, triggered=self._adjust_font_size))

        # 图标大小
        display_menu.addAction(QAction("图标大小...", self, triggered=self._adjust_icon_size))

        # 角色头像大小
        display_menu.addAction(QAction("角色头像大小...", self, triggered=self._adjust_char_icon_size))

        # 重置显示
        display_menu.addSeparator()
        display_menu.addAction(QAction("重置为默认", self, triggered=self._reset_display))

        settings_menu.addSeparator()

        # 使用和开发说明
        doc_action = settings_menu.addAction("使用和开发说明")
        doc_action.triggered.connect(self._show_docs)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = help_menu.addAction("关于风语")
        about_action.triggered.connect(lambda: QMessageBox.about(
            self, "关于风语",
            "风语 v2.0\n测风塔数据自动化工具\n\n"
            "自动从邮箱下载原始数据(.rld)\n"
            "解密转换为可读文本(.txt)\n\n"
            "v2.0: 动态表头匹配 + 显示设置 + 文件菜单增强\n\n"
            "开发者：曦儿"
        ))

        # 日志面板（全局）
        self.log_widget = LogSignal()

        # 标签页
        self.tabs = QTabWidget()
        self.tab_task = TaskPanel(self.config, self.executor, self.log_widget, self)
        self.tab_config = ConfigPanel(self.config, self.log_widget, self)
        self.tab_schedule = SchedulePanel(self.config, self.executor, self.log_widget)

        self.tabs.addTab(self.tab_task, "📋 数据任务")
        self.tabs.addTab(self.tab_config, "⚙ 配置")
        self.tabs.addTab(self.tab_schedule, "⏰ 定时任务")

        # 角色按钮栏
        self.char_bar_widget, self.char_bar_layout, self.char_buttons = self._build_char_bar()

        # 把标签页和图标栏包在一起
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)
        top_layout.addWidget(self.tabs)
        top_layout.addWidget(self.char_bar_widget)

        # 分割器：上部（标签页+图标栏） + 下部（日志）
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(self.log_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 启动日志
        self.log_widget.append_log("风语 v2.0 启动", "info")
        self.log_widget.append_log(f"[图标] 加载了 {len(self.char_buttons)} 个角色头像", "info")
        self.log_widget.append_log(f"配置文件: {self.config.config_path}", "info")
        self.log_widget.append_log(f"数据目录: {self.config.data_root}", "info")
        if os.path.exists(self.config.excel_path):
            self.log_widget.append_log("✅ 测风塔信息表已找到", "ok")
        else:
            self.log_widget.append_log("⚠ 测风塔信息表未找到，请检查配置", "warn")

        # 加载默认主题：念头通达
        self._load_theme("fanren_xiuxian")

        # 应用显示设置
        self._apply_display_settings()

    def _build_char_bar(self):
        """构建角色按钮栏，返回 (widget, layout, buttons) 以便后续调整大小"""
        import random

        char_bar_widget = QWidget()
        char_bar = QHBoxLayout(char_bar_widget)
        char_bar.setContentsMargins(0, 0, 0, 0)
        char_bar.setSpacing(6)

        # PyInstaller资源路径
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 加载台词
        quotes_dict = {}
        quote_path = os.path.join(base, "resources", "icons", "quotes.txt")
        if os.path.exists(quote_path):
            with open(quote_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "：" in line or ":" in line:
                        sep = "：" if "：" in line else ":"
                        name, quote = line.split(sep, 1)
                        name = name.strip()
                        if name not in quotes_dict:
                            quotes_dict[name] = []
                        quotes_dict[name].append(quote.strip())

        char_dir = os.path.join(base, "resources", "icons", "characters")

        # 文件名→中文角色名 对照表
        name_map = {
            "hanli": "韩立", "yinyue": "银月", "songyu": "宋玉",
            "ziling": "紫灵", "liuyu": "柳玉", "yanruyan": "燕如焉",
            "yuanyao": "元瑶", "tihun": "啼魂", "meining": "梅凝",
            "xuangu": "玄骨", "mupeiling": "慕沛灵", "nangongwan": "南宫婉",
        }

        buttons = []
        count = 0
        if os.path.isdir(char_dir):
            for fn in sorted(os.listdir(char_dir)):
                if fn.endswith(".png"):
                    name = fn.replace(".png", "")
                    display_name = name_map.get(name, name)

                    btn = QPushButton()
                    icon_size = self.config.char_icon_size
                    btn_size = icon_size + 24
                    btn.setFixedSize(btn_size, btn_size)
                    btn.setIcon(QIcon(os.path.join(char_dir, fn)))
                    btn.setIconSize(QSize(icon_size, icon_size))
                    btn.setToolTip("")
                    btn.setStyleSheet("""
                        QPushButton { border: 2px solid #555; border-radius: 8px; background: transparent; }
                        QPushButton:hover { border-color: #aaa; background: rgba(255,255,255,0.1); }
                    """)

                    # 鼠标悬停弹气泡
                    class QuoteLabel(QLabel):
                        def __init__(self_ql, parent_btn, char_name, quotes):
                            super().__init__(parent_btn.window())
                            self_ql.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
                            self_ql.setAttribute(Qt.WA_ShowWithoutActivating)
                            self_ql.setStyleSheet("""
                                QLabel { background: #fffef0; color: #3a3020; border: 2px solid #c8b898;
                                         border-radius: 10px; padding: 10px 14px; font-size: 14px;
                                         font-family: 'KaiTi','STKaiti','Microsoft YaHei'; }
                            """)
                            self_ql.quotes = quotes
                            self_ql.hide()
                        def show_quote(self_ql, pos):
                            if self_ql.quotes:
                                txt = random.choice(self_ql.quotes)
                                self_ql.setText(txt)
                                self_ql.adjustSize()
                                self_ql.move(pos)
                                self_ql.show()
                                QTimer.singleShot(5000, self_ql.hide)

                    popup = QuoteLabel(btn, display_name, quotes_dict.get(display_name, []))
                    btn.quote_label = popup
                    btn.enterEvent = lambda e, b=btn: b.quote_label.show_quote(
                        b.mapToGlobal(QPoint(-60, -50)))
                    btn.leaveEvent = lambda e, b=btn: b.quote_label.hide()

                    char_bar.addWidget(btn)
                    buttons.append(btn)
                    count += 1
        char_bar.addStretch()

        return char_bar_widget, char_bar, buttons

    def _reload_config(self):
        """重新加载配置 + 刷新塔列表"""
        from core.config_loader import Config
        self.config = Config()
        self.executor.config = self.config
        # 刷新各面板
        self.tab_task.config = self.config
        self.tab_task.executor = self.executor
        self.tab_task._load_towers()
        self.tab_config.config = self.config
        self.log_widget.append_log("配置已重新加载", "info")

    # ============================================================
    # 文件菜单动作
    # ============================================================

    def _open_data_dir(self):
        """在资源管理器中打开数据存储根目录"""
        path = self.config.data_root
        if path and os.path.isdir(path):
            subprocess.Popen(['explorer', path])
            self.log_widget.append_log(f"打开数据目录: {path}", "info")
        else:
            QMessageBox.warning(self, "提示", f"数据目录不存在:\n{path}")

    def _open_tower_dir(self):
        """打开选中塔的文件夹"""
        tower = self.tab_task.get_selected_tower()
        if not tower:
            # 尝试取第一个选中的塔
            if self.tab_task.selected_towers:
                tower = self.tab_task.selected_towers[0]
        if not tower:
            QMessageBox.warning(self, "提示", "请先在列表中选择一个塔")
            return

        path = os.path.join(self.config.data_root, tower["short_code"])
        if os.path.isdir(path):
            subprocess.Popen(['explorer', path])
            self.log_widget.append_log(f"打开塔目录: {path}", "info")
        else:
            reply = QMessageBox.question(
                self, "提示",
                f"塔 {tower['short_code']} 的目录尚不存在:\n{path}\n\n是否创建？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                os.makedirs(path, exist_ok=True)
                subprocess.Popen(['explorer', path])
                self.log_widget.append_log(f"创建并打开塔目录: {path}", "ok")

    def _open_txt_dir(self):
        """打开选中塔的 TXT 输出目录"""
        tower = self.tab_task.get_selected_tower()
        if not tower and self.tab_task.selected_towers:
            tower = self.tab_task.selected_towers[0]
        if not tower:
            QMessageBox.warning(self, "提示", "请先在列表中选择一个塔")
            return

        path = os.path.join(self.config.data_root, tower["short_code"], "TXT输出")
        if os.path.isdir(path):
            subprocess.Popen(['explorer', path])
            self.log_widget.append_log(f"打开 TXT 输出目录: {path}", "info")
        else:
            QMessageBox.information(self, "提示", f"TXT 输出目录尚不存在:\n{path}\n\n请先执行一次解密转换任务。")

    def _open_excel(self):
        """用默认程序打开 Excel 表格"""
        path = self.config.excel_path
        if path and os.path.exists(path):
            os.startfile(path)
            self.log_widget.append_log(f"打开 Excel: {path}", "info")
        else:
            QMessageBox.warning(self, "提示", f"Excel 文件不存在:\n{path}")

    # ============================================================
    # 显示设置
    # ============================================================

    def _adjust_font_size(self):
        """调整字体大小"""
        from PyQt5.QtWidgets import QInputDialog
        val, ok = QInputDialog.getInt(
            self, "字体大小", "字体大小 (8-20):",
            self.config.font_size, 8, 20, 1
        )
        if ok:
            self.config.font_size = val
            self.config.save()
            self._apply_display_settings()
            self.log_widget.append_log(f"字体大小已设为 {val}", "ok")

    def _adjust_icon_size(self):
        """调整图标大小"""
        from PyQt5.QtWidgets import QInputDialog
        val, ok = QInputDialog.getInt(
            self, "图标大小", "按钮图标大小 (24-96):",
            self.config.icon_size, 24, 96, 4
        )
        if ok:
            self.config.icon_size = val
            self.config.save()
            self._apply_display_settings()
            self.log_widget.append_log(f"图标大小已设为 {val}", "ok")

    def _adjust_char_icon_size(self):
        """调整角色头像大小"""
        from PyQt5.QtWidgets import QInputDialog
        val, ok = QInputDialog.getInt(
            self, "角色头像大小", "角色头像大小 (48-128):",
            self.config.char_icon_size, 48, 128, 4
        )
        if ok:
            self.config.char_icon_size = val
            self.config.save()
            self._apply_display_settings()
            self.log_widget.append_log(f"角色头像大小已设为 {val}", "ok")

    def _reset_display(self):
        """重置显示设置为默认"""
        self.config.font_size = 10
        self.config.icon_size = 48
        self.config.char_icon_size = 72
        self.config.save()
        self._apply_display_settings()
        self.log_widget.append_log("显示设置已重置为默认", "ok")

    def _apply_display_settings(self):
        """应用当前显示设置到界面"""
        font_size = self.config.font_size
        icon_size = self.config.icon_size
        char_size = self.config.char_icon_size

        # 全局字体
        app = QApplication.instance()
        font = app.font()
        font.setPointSize(font_size)
        app.setFont(font)

        # 日志面板字体
        self.log_widget.setFont(QFont("Consolas", font_size))

        # 角色头像大小
        btn_size = char_size + 24
        for btn in getattr(self, 'char_buttons', []):
            btn.setFixedSize(btn_size, btn_size)
            btn.setIconSize(QSize(char_size, char_size))

    # ============================================================
    # 主题和文档
    # ============================================================

    def _load_theme(self, name):
        import os
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "resources", "themes", f"{name}.qss")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())
            self.log_widget.append_log(f"主题已切换: {name}", "info")
        else:
            self.log_widget.append_log(f"主题文件不存在: {path}", "warn")

    def _show_docs(self):
        """弹窗显示使用和开发说明"""
        import os
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "resources", "开发说明.md"),
        ]
        found = None
        for p in candidates:
            if os.path.exists(p):
                found = p
                break

        if found:
            try:
                with open(found, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = "无法读取文档文件"
        else:
            content = (
                "# 风语 v2.0 开发说明\n\n"
                "项目结构见 D:\\WindWatcher\\resources\\开发说明.md\n\n"
                "## 核心模块\n"
                "core/config_loader.py — 读取config.json和Excel（v2.0: 动态表头匹配）\n"
                "core/executor.py — 任务编排\n"
                "core/email_fetcher.py — POP3邮箱下载\n"
                "core/integrity_checker.py — 本地完整性检查\n"
                "core/converter.py — .rld解密转换\n\n"
                "## 界面\n"
                "ui/main_window.py — 主窗口+面板+角色栏（v2.0: 文件菜单+显示设置）\n\n"
                "## 主题\n"
                "resources/themes/ — QSS主题文件\n"
                "修改后重新打包即可生效\n\n"
                "## 打包命令\n"
                "pyinstaller --onefile --windowed --name=\"风语\" "
                "--add-data=\"resources;resources\" --hidden-import=nrgpy main.py"
            )

        dlg = QMessageBox(self)
        dlg.setWindowTitle("使用和开发说明")
        dlg.setText("")
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(content)
        te.setMinimumSize(700, 500)
        dlg.layout().addWidget(te, 0, 0, 1, dlg.layout().columnCount())
        dlg.exec_()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 全局样式
    app.setStyleSheet("""
        QMainWindow { background-color: #252526; }
        QGroupBox {
            font-weight: bold; border: 1px solid #333;
            border-radius: 6px; margin-top: 10px; padding-top: 16px;
            color: #ccc;
        }
        QGroupBox::title {
            subcontrol-origin: margin; left: 12px; padding: 0 6px;
        }
        QTreeWidget {
            background-color: #1e1e1e; color: #d4d4d4;
            border: 1px solid #333; border-radius: 4px;
        }
        QTreeWidget::item:hover { background-color: #2a2d2e; }
        QPushButton {
            padding: 6px 16px; border-radius: 4px;
            background-color: #333; color: #ccc; border: 1px solid #555;
        }
        QPushButton:hover { background-color: #444; }
        QTabWidget::pane { border: 1px solid #333; background-color: #1e1e1e; }
        QTabBar::tab {
            background-color: #2d2d2d; color: #999; padding: 8px 20px;
            border: 1px solid #333; border-bottom: none;
        }
        QTabBar::tab:selected { background-color: #1e1e1e; color: #fff; }
        QLineEdit, QSpinBox, QComboBox {
            background-color: #3c3c3c; color: #d4d4d4;
            border: 1px solid #555; border-radius: 3px; padding: 4px 8px;
        }
        QDateEdit {
            background-color: #3c3c3c; color: #d4d4d4;
            border: 1px solid #555; border-radius: 3px; padding: 4px;
        }
        QLabel { color: #ccc; }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
