# pages/session_interface.py
# coding:utf-8
import os
import time

# 🛡️ 核心防崩溃护盾：强行禁用 Oracle 底层信号捕获，彻底杜绝内嵌浏览器引发的 ORA-24550 闪退
os.environ["DIAG_ADR_ENABLED"] = "OFF"
os.environ["DIAG_SIGHANDLER_ENABLED"] = "FALSE"
os.environ["DIAG_CRASH_HANDLING_ENABLED"] = "FALSE"

import paramiko
import pymysql
import re
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtWidgets import QWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QApplication, QDialog, \
    QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from qfluentwidgets import InfoBar, Dialog, MessageBoxBase, SubtitleLabel, LineEdit, RoundMenu, Action, FluentIcon, \
    TableWidget

from ui.ui_session import Ui_Session
from core.ConnOracle import ConnOracle
from config.config import SERVER_DB_CONFIG


# ================= 弹窗对话框区域 =================

class DBEditDialog(MessageBoxBase):
    def __init__(self, parent=None, db_data=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(350)
        self.titleLabel = SubtitleLabel('数据库服务器配置', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.name_input = LineEdit(self.widget)
        self.name_input.setPlaceholderText("显示名称 (例如: 核心交易库)")
        self.viewLayout.addWidget(self.name_input)

        self.ip_input = LineEdit(self.widget)
        self.ip_input.setPlaceholderText("IP 地址")
        self.viewLayout.addWidget(self.ip_input)

        self.port_input = LineEdit(self.widget)
        self.port_input.setPlaceholderText("端口 (默认 22)")
        self.port_input.setText("22")
        self.viewLayout.addWidget(self.port_input)

        self.user_input = LineEdit(self.widget)
        self.user_input.setText("root")
        self.viewLayout.addWidget(self.user_input)

        self.pwd_input = LineEdit(self.widget)
        self.pwd_input.setPlaceholderText("密码")
        self.pwd_input.setEchoMode(LineEdit.Password)
        self.viewLayout.addWidget(self.pwd_input)

        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')

        if db_data:
            self.name_input.setText(db_data.get("name", ""))
            self.ip_input.setText(db_data.get("server_ip", ""))
            self.port_input.setText(str(db_data.get("port", 22)))
            self.user_input.setText(db_data.get("linux_user", ""))
            self.pwd_input.setText(db_data.get("linux_pwd", ""))

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "server_ip": self.ip_input.text().strip(),
            "port": self.port_input.text().strip() or "22",
            "linux_user": self.user_input.text().strip(),
            "linux_pwd": self.pwd_input.text().strip()
        }


class DBConnectionTesterThread(QThread):
    result_signal = pyqtSignal(int, bool, str)

    def __init__(self, row, db_data):
        super().__init__()
        self.row = row
        self.db_data = db_data

    def run(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.db_data['server_ip'],
                port=self.db_data['port'],
                username=self.db_data['linux_user'],
                password=self.db_data['linux_pwd'],
                timeout=3
            )
            self.result_signal.emit(self.row, True, "")
        except Exception as e:
            self.result_signal.emit(self.row, False, str(e))
        finally:
            client.close()


class DBInfoDialog(MessageBoxBase):
    def __init__(self, db_list, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(700)
        self.widget.setMinimumHeight(400)

        self.titleLabel = SubtitleLabel('数据库详情 (支持右键或 Ctrl+C 复制)', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.table = TableWidget(self.widget)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['数据库名', 'IP 地址', '端口', '账号', '密码'])
        self.table.verticalHeader().hide()

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableView::item:selected { background-color: #D9EBF9; color: #000000; }")

        self.table.setRowCount(len(db_list))
        for i, data in enumerate(db_list):
            self.table.setItem(i, 0, QTableWidgetItem(str(data.get('name', ''))))
            self.table.setItem(i, 1, QTableWidgetItem(str(data.get('server_ip', ''))))
            self.table.setItem(i, 2, QTableWidgetItem(f"{data.get('port', '')}"))
            self.table.setItem(i, 3, QTableWidgetItem(str(data.get('linux_user', ''))))
            self.table.setItem(i, 4, QTableWidgetItem(str(data.get('linux_pwd', ''))))

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        self.viewLayout.addWidget(self.table)
        self.yesButton.setText('关闭')
        self.cancelButton.hide()

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        menu = RoundMenu(parent=self)
        copy_action = Action(FluentIcon.COPY, "复制选中内容 (Ctrl+C)")
        copy_action.triggered.connect(lambda: QTimer.singleShot(50, self.copy_selected))
        menu.addAction(copy_action)
        menu.exec(self.table.mapToGlobal(pos))

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            self.copy_selected()
        else:
            super().keyPressEvent(event)

    def copy_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items: return

        rows = sorted(list(set(item.row() for item in selected_items)))
        cols = sorted(list(set(item.column() for item in selected_items)))

        copy_text = ""
        for r in rows:
            row_data = []
            for c in cols:
                item = self.table.item(r, c)
                if item and item in selected_items:
                    row_data.append(item.text())
            if row_data:
                copy_text += "\t".join(row_data) + "\n"

        QApplication.clipboard().setText(copy_text.strip())
        safe_parent = self.parent().window() if self.parent() else self.window()
        InfoBar.success("已复制", "内容已成功复制到系统剪贴板", parent=safe_parent)


# ================= 🌟 核心：内嵌 DeepSeek 分析器 (支持记住登录、深度思考、状态机) =================

class DeepSeekAnalyzerDialog(QDialog):
    def __init__(self, sql_text, plan_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✨ DeepSeek DBA 专家分析器 (内置独立浏览器)")

        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.resize(1300, 850)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.profile = QWebEngineProfile.defaultProfile()
        chrome_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        self.profile.setHttpUserAgent(chrome_ua)

        cache_path = os.path.abspath(os.path.join(os.getcwd(), "web_cache", "deepseek"))
        self.profile.setCachePath(cache_path)
        self.profile.setPersistentStoragePath(cache_path)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)

        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(self.profile, self.view)

        settings = self.page.settings()
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

        self.view.setPage(self.page)
        self.layout.addWidget(self.view)

        self.prompt = (
            "你是一个资深的 Oracle DBA 专家。请分析以下 SQL 及执行计划，"
            "指出潜在的性能瓶颈（如全表扫描、笛卡尔积、隐式转换等）并给出优化建议：\n\n"
            f"【SQL 语句】\n{sql_text}\n\n"
            f"【执行计划】\n{plan_text}"
        )

        QApplication.clipboard().setText(self.prompt)
        self.page.loadFinished.connect(self.on_load_finished)
        self.view.load(QUrl("https://chat.deepseek.com/"))

    def on_load_finished(self, success):
        if not success: return

        safe_prompt = self.prompt.replace('\\', '\\\\').replace('\n', '\\n').replace('`', '\\`').replace("'", "\\'")

        js_code = f"""
        (function() {{
            let attempts = 0;
            let step = 0; 

            let fillInterval = setInterval(function() {{
                if (document.visibilityState !== 'visible') return;
                attempts++;

                if (step === 0) {{
                    let newChatBtn = Array.from(document.querySelectorAll('div, button, span')).find(el => 
                        el.textContent && (el.textContent.trim() === '开启新对话' || el.textContent.trim() === '新对话')
                    );
                    if (newChatBtn) {{
                        (newChatBtn.closest('button') || newChatBtn.closest('div[role="button"]') || newChatBtn).click();
                        step = 1; attempts = 0; return;
                    }}
                    if (attempts > 3) {{ step = 1; attempts = 0; }}
                }}

                if (step === 1) {{
                    let expertBtn = Array.from(document.querySelectorAll('div, button, span')).find(el => 
                        el.textContent && (el.textContent.trim() === '深度思考' || el.textContent.trim() === '专家模式')
                    );
                    if (expertBtn) {{
                        let clickTarget = expertBtn.closest('button') || expertBtn.closest('div[role="switch"]') || expertBtn.closest('div[role="button"]') || expertBtn;
                        let parentHtml = expertBtn.parentElement ? expertBtn.parentElement.innerHTML : "";
                        if (!parentHtml.includes('active') && !parentHtml.includes('checked')) {{
                            clickTarget.click();
                        }}
                        step = 2; attempts = 0; return;
                    }}
                    if (attempts > 6) {{ step = 2; attempts = 0; }}
                }}

                if (step === 2) {{
                    let textarea = document.querySelector('#chat-input') || document.querySelector('textarea') || document.querySelector('div[contenteditable="true"]');
                    if (textarea) {{
                        textarea.focus();
                        let inserted = document.execCommand('insertText', false, '{safe_prompt}');
                        if (!inserted || !textarea.value) {{
                            textarea.value = '{safe_prompt}';
                            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                        step = 3; attempts = 0; return;
                    }}
                    if (attempts > 15) clearInterval(fillInterval);
                }}

                if (step === 3) {{
                    let sendBtn = document.querySelector('div[role="button"][aria-label*="发送"]') || document.querySelector('button[aria-label*="发送"]') || document.querySelector('.ds-send-button');
                    let textarea = document.querySelector('#chat-input') || document.querySelector('textarea');

                    if (sendBtn && !sendBtn.getAttribute('aria-disabled')) {{
                        (sendBtn.closest('button') || sendBtn).click();
                        clearInterval(fillInterval);
                    }} else if (textarea) {{
                        textarea.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}}));
                        clearInterval(fillInterval);
                    }}
                    if (attempts > 15) clearInterval(fillInterval);
                }}
            }}, 600);
        }})();
        """
        self.page.runJavaScript(js_code)


# ================= 🌟 核心主界面管理器 =================

class SessionInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Session()
        self.ui.setupUi(self)
        self.setObjectName("Session Interface")

        self.db_data_list = []
        self.active_testers = []
        self.current_sessions_cache = {}
        self.current_db_conn_info = None

        self.load_databases()

        self._bind_events()

    def _bind_events(self):
        self.ui.db_table.itemDoubleClicked.connect(self.load_sessions)

        self.ui.btn_add.clicked.connect(self.add_db)
        self.ui.btn_copy.clicked.connect(self.copy_db)
        self.ui.btn_edit.clicked.connect(self.edit_db)
        self.ui.btn_del.clicked.connect(self.delete_db)
        self.ui.btn_test.clicked.connect(self.test_connection)
        self.ui.search_input.textChanged.connect(self.filter_databases)
        self.ui.db_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.db_table.customContextMenuRequested.connect(self.show_context_menu)

        self.ui.btn_refresh.clicked.connect(self.load_sessions)
        self.ui.combo_status.currentIndexChanged.connect(self.load_sessions)
        self.ui.btn_kill.clicked.connect(self.kill_selected_sessions)

        self.ui.btn_ai_analysis.clicked.connect(self.run_ai_analysis)

        self.ui.combo_plan_format.currentIndexChanged.connect(self.refresh_current_tab)
        self.ui.session_table.itemSelectionChanged.connect(self.refresh_current_tab)
        self.ui.tab_widget.currentChanged.connect(self.refresh_current_tab)
        self.ui.chk_bind.stateChanged.connect(self.refresh_current_tab)

    def show_context_menu(self, pos):
        item = self.ui.db_table.itemAt(pos)
        if not item: return
        menu = RoundMenu(parent=self)
        info_action = Action(FluentIcon.INFO, "查看数据库详情")
        copy_action = Action(FluentIcon.COPY, "复制选中配置")
        edit_action = Action(FluentIcon.EDIT, "修改连接配置")
        del_action = Action(FluentIcon.DELETE, "删除此配置")

        info_action.triggered.connect(lambda: QTimer.singleShot(50, self.view_db_info))
        copy_action.triggered.connect(lambda: QTimer.singleShot(50, self.copy_db))
        edit_action.triggered.connect(lambda: QTimer.singleShot(50, self.edit_db))
        del_action.triggered.connect(lambda: QTimer.singleShot(50, self.delete_db))

        menu.addAction(info_action)
        menu.addSeparator()
        menu.addAction(copy_action)
        menu.addAction(edit_action)
        menu.addSeparator()
        menu.addAction(del_action)
        menu.exec(self.ui.db_table.mapToGlobal(pos))

    def view_db_info(self):
        selected_rows = self.ui.db_table.selectionModel().selectedRows()
        if not selected_rows: return
        selected_data = [self.db_data_list[m.row()] for m in selected_rows if not self.ui.db_table.isRowHidden(m.row())]
        if selected_data:
            dlg = DBInfoDialog(selected_data, self.window())
            dlg.exec()

    def add_db(self):
        dlg = DBEditDialog(self.window())
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("""
                              INSERT INTO db_server (server_ip, name, oracle_user, oracle_pwd, linux_user, linux_pwd, port)
                              VALUES (%s, %s, %s, %s, %s, %s, %s)
                              """, (data["server_ip"], data["name"], "system", "2742848", data["linux_user"],
                                    data["linux_pwd"], data["port"]))
                conn.commit()
                conn.close()
                self.load_databases()
            except Exception as e:
                InfoBar.error('添加失败', str(e), parent=self.window())

    def copy_db(self):
        row = self.ui.db_table.currentRow()
        if row < 0: return
        db_data = self.db_data_list[row].copy()
        db_data['name'] = db_data['name'] + " - 副本"
        dlg = DBEditDialog(self.window(), db_data)
        dlg.titleLabel.setText("复制服务器配置")
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("""
                              INSERT INTO db_server (server_ip, name, oracle_user, oracle_pwd, linux_user, linux_pwd, port)
                              VALUES (%s, %s, %s, %s, %s, %s, %s)
                              """, (data["server_ip"], data["name"], "system", "2742848", data["linux_user"],
                                    data["linux_pwd"], data["port"]))
                conn.commit()
                conn.close()
                self.load_databases()
            except:
                pass

    def edit_db(self):
        row = self.ui.db_table.currentRow()
        if row < 0: return
        db_data = self.db_data_list[row]
        dlg = DBEditDialog(self.window(), db_data)
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("""
                              UPDATE db_server
                              SET server_ip=%s,
                                  name=%s,
                                  linux_user=%s,
                                  linux_pwd=%s,
                                  port=%s
                              WHERE id = %s
                              """,
                              (data["server_ip"], data["name"], data["linux_user"], data["linux_pwd"], data["port"],
                               db_data["id"]))
                conn.commit()
                conn.close()
                self.load_databases()
            except Exception as e:
                InfoBar.error('更新失败', str(e), parent=self.window())

    def delete_db(self):
        row = self.ui.db_table.currentRow()
        if row < 0: return
        db_data = self.db_data_list[row]
        w = Dialog("确认删除", f"确定删除数据库 {db_data['name']} 吗？", self.window())
        if w.exec():
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("DELETE FROM db_server WHERE id=%s", (db_data['id'],))
                conn.commit()
                conn.close()
                self.load_databases()
            except Exception as e:
                InfoBar.error('删除失败', str(e), parent=self.window())

    def filter_databases(self, text):
        search_text = text.lower()
        for i in range(self.ui.db_table.rowCount()):
            name = self.ui.db_table.item(i, 1).text().lower()
            ip = self.ui.db_table.item(i, 2).text().lower()
            self.ui.db_table.setRowHidden(i, not ((search_text in name) or (search_text in ip)))

    def test_connection(self):
        selected_rows = self.ui.db_table.selectionModel().selectedRows()
        if not selected_rows:
            InfoBar.warning("提示", "请先选中要测试的数据库！", parent=self.window())
            return
        for i in range(self.ui.db_table.rowCount()):
            item = QTableWidgetItem("-")
            item.setTextAlignment(Qt.AlignCenter)
            self.ui.db_table.setItem(i, 0, item)
        for model_index in selected_rows:
            row = model_index.row()
            if self.ui.db_table.isRowHidden(row): continue
            wait_item = QTableWidgetItem("⏳")
            wait_item.setTextAlignment(Qt.AlignCenter)
            self.ui.db_table.setItem(row, 0, wait_item)
            db_data = self.db_data_list[row]
            tester = DBConnectionTesterThread(row, db_data)
            tester.result_signal.connect(self.on_test_result)
            tester.start()
            self.active_testers.append(tester)

    def on_test_result(self, row, success, error_msg):
        res_item = QTableWidgetItem("✅" if success else "❌")
        res_item.setTextAlignment(Qt.AlignCenter)
        if not success: res_item.setToolTip(f"连接失败: {error_msg}")
        self.ui.db_table.setItem(row, 0, res_item)

    def load_databases(self):
        self.ui.db_table.setRowCount(0)
        self.db_data_list.clear()
        try:
            conn = pymysql.connect(**SERVER_DB_CONFIG)
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM db_server")
                for i, row in enumerate(cursor.fetchall()):
                    self.ui.db_table.insertRow(i)
                    st_item = QTableWidgetItem("-")
                    st_item.setTextAlignment(Qt.AlignCenter)
                    self.ui.db_table.setItem(i, 0, st_item)
                    name_item = QTableWidgetItem(row['name'])
                    name_item.setToolTip(row['name'])
                    self.ui.db_table.setItem(i, 1, name_item)
                    self.ui.db_table.setItem(i, 2, QTableWidgetItem(row['server_ip']))
                    self.ui.db_table.setItem(i, 3, QTableWidgetItem(row['linux_user']))
                    self.db_data_list.append(row)
            conn.close()
        except Exception as e:
            InfoBar.error('数据库连接失败', str(e), parent=self.window())

    def load_sessions(self):
        row = self.ui.db_table.currentRow()
        if row < 0:
            InfoBar.warning("提示", "请先在左侧选择一台目标数据库！", parent=self.window())
            return

        self.current_db_conn_info = self.db_data_list[row]
        status_filter = self.ui.combo_status.currentText().upper()
        status_clause = ""
        if status_filter != "ALL":
            status_clause = f"AND status = '{status_filter}'"

            # 使用 sql_exec_start 作为 SQL 执行时间，logon_time 作为登录时间
            # 优化排序：让正在执行的 (sql_exec_start 不为空) 排在最上面，一目了然！
            query = f"""
                    SELECT rownum rn, 
                           to_char(sql_exec_start, 'YYYY-MM-DD HH24:MI:SS') exec_start,
                           to_char(SYSDATE, 'YYYY-MM-DD HH24:MI:SS') logon_time,
                           machine, sid, serial#, username, status, program, 
                           sql_id, sql_child_number
                    FROM v$session 
                    WHERE username is not null {status_clause}
                    ORDER BY sql_exec_start DESC NULLS LAST, logon_time DESC
                """

            db = ConnOracle(
                username="system", password="2742848",
                host=self.current_db_conn_info['server_ip'], port=1521, service_name="orcl"
            )
            db.connectorcl()
            if not db.connection or not db.cursor:
                InfoBar.error("连接失败", "无法连接数据库获取会话", parent=self.window())
                return

            self.ui.session_table.setRowCount(0)
            self.current_sessions_cache.clear()

            try:
                records = db.fetch_all(query)
                if not records: return
                self.ui.session_table.setRowCount(len(records))
                for i, r in enumerate(records):
                    sql_id = str(r[9]) if r[9] else ""
                    child_num = str(r[10]) if r[10] is not None else "0"
                    cache_key = f"{r[4]}_{r[5]}"

                    preview_sql = ""
                    if sql_id:
                        sql_res = db.fetch_all(
                            f"SELECT substr(sql_text,1,100) FROM v$sql WHERE sql_id='{sql_id}' AND child_number={child_num}")
                        if sql_res and sql_res[0][0]:
                            preview_sql = sql_res[0][0].replace('\n', ' ').strip()

                    self.current_sessions_cache[cache_key] = {
                        "sid": r[4], "serial": r[5], "sql_id": sql_id, "child_number": child_num, "username": r[6]
                    }

                    # 处理空值：如果没有在执行，时间显示为横杠 '-'
                    exec_time = str(r[1]) if r[1] else "-"
                    logon_t = str(r[2]) if r[2] else "-"

                    items = [
                        str(r[0]),  # 0: 行号
                        sql_id,  # 1: SQL_ID
                        exec_time,  # 2: SQL 开始执行时间
                        logon_t,  # 3: 会话登录时间
                        str(r[3]),  # 4: machine
                        str(r[4]),  # 5: sid
                        str(r[5]),  # 6: serial#
                        str(r[6]),  # 7: username
                        str(r[7]),  # 8: status
                        str(r[8]),  # 9: program
                        preview_sql,  # 10: 截断 SQL
                        cache_key  # 11: 隐藏键
                    ]

                    for col_idx, val in enumerate(items):
                        self.ui.session_table.setItem(i, col_idx, QTableWidgetItem(val))
            except Exception as e:
                InfoBar.error("查询异常", str(e), parent=self.window())
            finally:
                db.disconnect()

    def refresh_current_tab(self):
        selected_rows = self.ui.session_table.selectionModel().selectedRows()

        self.ui.sql_text.setPlainText("")
        self.ui.plan_text.setPlainText("")
        self.ui.kill_table.setRowCount(0)
        self.ui.obj_table.setRowCount(0)

        if not selected_rows: return

        current_tab_index = self.ui.tab_widget.currentIndex()

        if current_tab_index == 0:
            self.fetch_sql_text(selected_rows)
        elif current_tab_index == 1:
            self.fetch_execution_plan_internal(selected_rows)
        elif current_tab_index == 2:
            self.preview_kill_session(selected_rows)
        elif current_tab_index == 3:
            self.fetch_statement_objects(selected_rows)

    def fetch_sql_text(self, selected_rows):
        first_row = selected_rows[0].row()
        # 注意：缓存 key 现在的索引是 11
        cache_key = self.ui.session_table.item(first_row, 11).text()
        sess_info = self.current_sessions_cache.get(cache_key)

        if not sess_info or not sess_info['sql_id']:
            self.ui.sql_text.setPlainText("-- 当前会话无活动 SQL --")
            return

        db = ConnOracle(
            username="system", password="2742848",
            host=self.current_db_conn_info['server_ip'], port=1521, service_name="orcl"
        )
        db.connectorcl()
        try:
            sql_res = db.fetch_all(
                f"SELECT sql_fulltext FROM v$sql WHERE sql_id='{sess_info['sql_id']}' AND child_number={sess_info['child_number']}")
            if not sql_res:
                sql_res = db.fetch_all(
                    f"SELECT sql_fulltext FROM v$sql WHERE sql_id='{sess_info['sql_id']}' and rownum<=1")
            if not sql_res: return
            full_sql = sql_res[0][0]
            if hasattr(full_sql, 'read'): full_sql = full_sql.read()

            if self.ui.chk_bind.isChecked():
                bind_query = f"SELECT name, value_string FROM v$sql_bind_capture WHERE sql_id='{sess_info['sql_id']}' AND child_number={sess_info['child_number']}"
                binds = db.fetch_all(bind_query)
                if binds:
                    # 按照变量名长度从大到小排序，防止 :B10 被 :B1 错误替换
                    binds_sorted = sorted(binds, key=lambda x: len(x[0]), reverse=True)
                    for b_name, b_val in binds_sorted:
                        if b_val is not None:
                            full_sql = re.sub(re.escape(b_name) + r'(?!\w)', f"'{b_val}'", full_sql)
                        else:
                            full_sql = re.sub(re.escape(b_name) + r'(?!\w)', "'NULL'", full_sql)

                leftover_binds = re.findall(r'(:[a-zA-Z0-9_]+)(?!\w)', full_sql)
                if leftover_binds:
                    leftover_binds = list(set(leftover_binds))
                    warning_comment = f"-- ⚠️ 提示：以下绑定变量未被 Oracle 捕获(处于SELECT列或非过滤函数中): {', '.join(leftover_binds)}\n\n"
                    full_sql = warning_comment + full_sql

            self.ui.sql_text.setPlainText(full_sql)
        except Exception as e:
            self.ui.sql_text.setPlainText(f"-- 提取 SQL 异常: {str(e)} --")
        finally:
            db.disconnect()

    def fetch_execution_plan_internal(self, selected_rows):
        first_row = selected_rows[0].row()
        cache_key = self.ui.session_table.item(first_row, 11).text()
        sess_info = self.current_sessions_cache.get(cache_key)

        if not sess_info or not sess_info['sql_id']: return
        fmt = self.ui.combo_plan_format.currentText()
        db = ConnOracle(
            username="system", password="2742848",
            host=self.current_db_conn_info['server_ip'], port=1521, service_name="orcl"
        )
        db.connectorcl()
        try:
            plan_query = f"""
                with t as (
                   select rownum rn, a.*
                   from (select * from table(dbms_xplan.display_cursor('{sess_info['sql_id']}', {sess_info['child_number']}, '{fmt}'))) a
                )
                select plan_table_output from t
                where t.rn >= (select min(rn) from t where plan_table_output like 'Plan hash value:%')
                ORDER BY rn
            """
            plan_records = db.fetch_all(plan_query)
            if plan_records:
                plan_str = "\n".join([r[0] if r[0] else "" for r in plan_records])
                self.ui.plan_text.setPlainText(plan_str)
            else:
                self.ui.plan_text.setPlainText("-- 无法从 shared pool 中获取该语句的执行计划 --")
        finally:
            db.disconnect()

    def preview_kill_session(self, selected_rows):
        self.ui.kill_table.setRowCount(0)
        for idx, model_index in enumerate(selected_rows):
            cache_key = self.ui.session_table.item(model_index.row(), 11).text()
            sess = self.current_sessions_cache.get(cache_key)
            if not sess: continue

            kill_sql = f"ALTER SYSTEM KILL SESSION '{sess['sid']},{sess['serial']}' IMMEDIATE;"
            self.ui.kill_table.insertRow(idx)
            self.ui.kill_table.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            self.ui.kill_table.setItem(idx, 1, QTableWidgetItem(kill_sql))

            status_item = QTableWidgetItem("⏳ 待执行")
            status_item.setForeground(Qt.gray)
            self.ui.kill_table.setItem(idx, 2, status_item)

    def kill_selected_sessions(self):
        selected_rows = self.ui.session_table.selectionModel().selectedRows()
        if not selected_rows:
            InfoBar.warning("提示", "请先在上方表格选中要终止的会话！", parent=self.window())
            return

        w = Dialog("风险操作确认", f"确定要强制终止选中的 {len(selected_rows)} 个会话吗？", self.window())
        if not w.exec(): return

        self.ui.tab_widget.setCurrentIndex(2)
        self.preview_kill_session(selected_rows)

        db = ConnOracle(
            username="system", password="2742848",
            host=self.current_db_conn_info['server_ip'], port=1521, service_name="orcl"
        )
        db.connectorcl()

        for i in range(self.ui.kill_table.rowCount()):
            kill_sql = self.ui.kill_table.item(i, 1).text().replace(";", "").strip()
            try:
                if db.cursor:
                    db.cursor.execute(kill_sql)
                    res_item = QTableWidgetItem("✅ 成功")
                    res_item.setForeground(Qt.darkGreen)
                    self.ui.kill_table.setItem(i, 2, res_item)
            except Exception as e:
                res_item = QTableWidgetItem(f"❌ 失败: {str(e)}")
                res_item.setForeground(Qt.red)
                self.ui.kill_table.setItem(i, 2, res_item)

        if db.connection: db.disconnect()
        QTimer.singleShot(1500, self.load_sessions)

    def fetch_statement_objects(self, selected_rows):
        self.ui.obj_table.setRowCount(0)
        sql_ids = set()
        for index in selected_rows:
            cache_key = self.ui.session_table.item(index.row(), 11).text()
            sess_info = self.current_sessions_cache.get(cache_key)
            if sess_info and sess_info['sql_id']:
                sql_ids.add(sess_info['sql_id'])

        if not sql_ids: return
        sql_id_in_clause = ",".join([f"'{s}'" for s in sql_ids])

        query = f"""
            SELECT DISTINCT sql_id, object_owner, object_name, object_type 
            FROM v$sql_plan 
            WHERE sql_id IN ({sql_id_in_clause}) 
            AND object_name IS NOT NULL
            ORDER BY sql_id, object_owner, object_name
        """
        db = ConnOracle(
            username="system", password="2742848",
            host=self.current_db_conn_info['server_ip'], port=1521, service_name="orcl"
        )
        db.connectorcl()
        try:
            records = db.fetch_all(query)
            if records:
                self.ui.obj_table.setRowCount(len(records))
                for i, r in enumerate(records):
                    self.ui.obj_table.setItem(i, 0, QTableWidgetItem(str(r[0])))
                    self.ui.obj_table.setItem(i, 1, QTableWidgetItem(str(r[1])))
                    self.ui.obj_table.setItem(i, 2, QTableWidgetItem(str(r[2])))
                    self.ui.obj_table.setItem(i, 3, QTableWidgetItem(str(r[3])))
        finally:
            db.disconnect()

    def run_ai_analysis(self):
        sql_text = self.ui.sql_text.toPlainText().strip()
        plan_text = self.ui.plan_text.toPlainText().strip()

        if not plan_text or plan_text.startswith("--"):
            InfoBar.warning("提示", "当前没有可供分析的执行计划，请先在下方加载执行计划内容！", parent=self.window())
            return

        if not sql_text or sql_text.startswith("--"):
            selected_rows = self.ui.session_table.selectionModel().selectedRows()
            if selected_rows:
                first_row = selected_rows[0].row()
                cache_key = self.ui.session_table.item(first_row, 11).text()
                sess_info = self.current_sessions_cache.get(cache_key)
                if sess_info and sess_info['sql_id']:
                    db = ConnOracle(
                        username="system", password="2742848",
                        host=self.current_db_conn_info['server_ip'], port=1521, service_name="orcl"
                    )
                    db.connectorcl()
                    try:
                        sql_res = db.fetch_all(
                            f"SELECT sql_fulltext FROM v$sql WHERE sql_id='{sess_info['sql_id']}' AND child_number={sess_info['child_number']}")
                        if sql_res:
                            sql_text = sql_res[0][0]
                            if hasattr(sql_text, 'read'): sql_text = sql_text.read()
                    except:
                        pass
                    finally:
                        db.disconnect()

        if not sql_text: sql_text = "-- 未能成功捕获源 SQL --"

        InfoBar.success(
            "启动 AI 分析引擎",
            "正在为您打开内嵌版 DeepSeek...\n(自动执行：开启新对话 -> 选择深度思考 -> 分析执行计划)",
            duration=4000,
            parent=self.window()
        )

        self.deepseek_dlg = DeepSeekAnalyzerDialog(sql_text, plan_text, self.window())
        self.deepseek_dlg.show()