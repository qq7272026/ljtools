# pages/dataimp_interface.py
# coding:utf-8
import os
import csv
import time
from pathlib import Path

import pymysql
import subprocess
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (QWidget, QTableWidgetItem, QFileDialog, QListWidget,
                             QApplication, QHeaderView, QAbstractItemView)
from qfluentwidgets import (InfoBar, MessageBoxBase, SubtitleLabel, LineEdit, Dialog,
                            RoundMenu, Action, FluentIcon, PlainTextEdit, TableWidget, ComboBox)

from ui.ui_dataimp import Ui_DataImp
from core.ConnOracle import ConnOracle
from config.config import SERVER_DB_CONFIG
# 假设我们在 ljtoolbox 的某个逻辑文件中
base_dir = Path(__file__).resolve().parent
def init_db_table():
    try:
        conn = pymysql.connect(**SERVER_DB_CONFIG)
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS plsql_server (
                    databaseid INT AUTO_INCREMENT PRIMARY KEY,
                    databasename VARCHAR(100),
                    databaseip VARCHAR(50),
                    databaseport INT DEFAULT 1521,
                    databasesid VARCHAR(50),
                    databaseuser VARCHAR(50),
                    databasepassword VARCHAR(100)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"初始化表失败: {e}")


# ================= 弹窗对话框区域 =================

class DBInfoDialog(MessageBoxBase):
    def __init__(self, db_list, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(700)
        self.widget.setMinimumHeight(400)

        self.titleLabel = SubtitleLabel('数据库详情 (支持右键或 Ctrl+C 复制)', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.table = TableWidget(self.widget)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['数据库名', 'IP 地址', '端口/SID', '账号', '密码'])
        self.table.verticalHeader().hide()

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        # 👈 核心修复：为弹窗表格强行注入浅蓝色的选中高亮样式
        self.table.setStyleSheet("""
            QTableView::item:selected {
                background-color: #D9EBF9;
                color: #000000;
            }
        """)
        self.table.setRowCount(len(db_list))
        for i, data in enumerate(db_list):
            self.table.setItem(i, 0, QTableWidgetItem(str(data.get('databasename', ''))))
            self.table.setItem(i, 1, QTableWidgetItem(str(data.get('databaseip', ''))))
            port_sid = f"{data.get('databaseport', '')}/{data.get('databasesid', '')}"
            self.table.setItem(i, 2, QTableWidgetItem(port_sid))
            self.table.setItem(i, 3, QTableWidgetItem(str(data.get('databaseuser', ''))))
            self.table.setItem(i, 4, QTableWidgetItem(str(data.get('databasepassword', ''))))

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
        # 👈 核心修复 2：使用 QTimer 延迟执行复制动作，防止 InfoBar 报错崩溃
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
        # 👈 核心修复：把 InfoBar 挂载到父级主窗口 (DataImpInterface) 上。
        # 这样即使你光速关掉这个弹窗，提示信息也会在后面的大背景上安稳地播完动画，再也不会崩溃了！
        safe_parent = self.parent().window() if self.parent() else self.window()
        InfoBar.success("已复制", "内容已成功复制到系统剪贴板", parent=safe_parent)


class DBEditDialog(MessageBoxBase):
    def __init__(self, parent=None, db_data=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(350)
        self.titleLabel = SubtitleLabel('Oracle 数据库配置', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.name_input = LineEdit(self.widget)
        self.name_input.setPlaceholderText("显示名称 (例如: 核心交易库)")
        self.viewLayout.addWidget(self.name_input)

        self.ip_input = LineEdit(self.widget)
        self.ip_input.setPlaceholderText("IP 地址")
        self.viewLayout.addWidget(self.ip_input)

        self.port_input = LineEdit(self.widget)
        self.port_input.setPlaceholderText("端口 (默认 1521)")
        self.port_input.setText("1521")
        self.viewLayout.addWidget(self.port_input)

        self.sid_input = LineEdit(self.widget)
        self.sid_input.setPlaceholderText("数据库 SID/服务名 (例如: orcl)")
        self.viewLayout.addWidget(self.sid_input)

        self.user_input = LineEdit(self.widget)
        self.user_input.setPlaceholderText("用户名")
        self.viewLayout.addWidget(self.user_input)

        self.pwd_input = LineEdit(self.widget)
        self.pwd_input.setPlaceholderText("密码")
        self.pwd_input.setEchoMode(LineEdit.Password)
        self.viewLayout.addWidget(self.pwd_input)

        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')

        if db_data:
            self.name_input.setText(db_data.get("databasename", ""))
            self.ip_input.setText(db_data.get("databaseip", ""))
            self.port_input.setText(str(db_data.get("databaseport", 1521)))
            self.sid_input.setText(db_data.get("databasesid", ""))
            self.user_input.setText(db_data.get("databaseuser", ""))
            self.pwd_input.setText(db_data.get("databasepassword", ""))

    def get_data(self):
        return {
            "databasename": self.name_input.text().strip(),
            "databaseip": self.ip_input.text().strip(),
            "databaseport": int(self.port_input.text().strip() or 1521),
            "databasesid": self.sid_input.text().strip(),
            "databaseuser": self.user_input.text().strip(),
            "databasepassword": self.pwd_input.text().strip()
        }


class TableSelectDialog(MessageBoxBase):
    def __init__(self, table_list, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(350)
        self.widget.setMinimumHeight(450)
        self.titleLabel = SubtitleLabel('选择数据库表', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.search_input = LineEdit(self.widget)
        self.search_input.setPlaceholderText("搜索表名...")
        self.search_input.textChanged.connect(self.filter_tables)
        self.viewLayout.addWidget(self.search_input)

        self.list_widget = QListWidget(self.widget)
        self.list_widget.addItems(table_list)
        self.list_widget.itemDoubleClicked.connect(self.on_double_click)
        self.viewLayout.addWidget(self.list_widget)

        self.selected_table = ""
        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

    def filter_tables(self, text):
        search_text = text.upper()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(search_text not in item.text().upper())

    def on_double_click(self, item):
        self.selected_table = item.text()
        self.accept()


# ================= SQL*Loader 日志弹窗与执行线程 =================

class SqlldrLogDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(650)
        self.widget.setMinimumHeight(450)
        self.titleLabel = SubtitleLabel('正在执行 SQL*Loader...', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.text_edit = PlainTextEdit(self.widget)
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QPlainTextEdit {
                font-family: 'Consolas', monospace; 
                font-size: 13px; 
                background: #1E1E1E; 
                color: #4AF626; 
                padding: 10px;
                border-radius: 6px;
            }
        """)
        self.viewLayout.addWidget(self.text_edit)

        self.yesButton.setText('关闭')
        self.yesButton.setEnabled(False)
        self.cancelButton.hide()

    def append_log(self, text):
        self.text_edit.appendPlainText(text.strip())

    def on_finished(self, return_code):
        self.yesButton.setEnabled(True)
        if return_code == 0:
            self.titleLabel.setText('SQL*Loader 执行完成 ✅')
        else:
            self.titleLabel.setText(f'SQL*Loader 执行异常 (退出码: {return_code}) ❌')


class SqlldrRunnerThread(QThread):
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, cmd, oracle_home, bin_path):
        super().__init__()
        self.cmd = cmd
        self.oracle_home = oracle_home
        self.bin_path = bin_path

    def run(self):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # ⭐ 核心修复 1：强行注入内置客户端的环境变量！
            env = os.environ.copy()
            env["ORACLE_HOME"] = self.oracle_home
            # 必须将内置的 bin 目录放入 PATH 首位，供 sqlldr 寻找 oci.dll
            env["PATH"] = self.bin_path + os.pathsep + env.get("PATH", "")
            # 指定字符集，防止中文提示乱码 (对应你完整的 mesg 字典)
            env["NLS_LANG"] = "SIMPLIFIED CHINESE_CHINA.ZHS16GBK"
            process = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors='ignore',
                startupinfo=startupinfo,
                env=env  # 👈 极其关键：把绑定好的环境传给子进程
            )

            for line in iter(process.stdout.readline, ''):
                self.output_signal.emit(line)

            process.stdout.close()
            process.wait()
            self.finished_signal.emit(process.returncode)

        except FileNotFoundError:
            self.output_signal.emit("[错误] 无法找到 'sqlldr' 命令：{self.cmd[0]}")
            self.output_signal.emit("请确保您的电脑已经安装了 Oracle Client，并且将其添加到了系统的环境变量 (Path) 中。")
            self.finished_signal.emit(-1)
        except Exception as e:
            self.output_signal.emit(f"[未知异常]: {str(e)}")
            self.finished_signal.emit(-1)


class DBConnectionTesterThread(QThread):
    result_signal = pyqtSignal(int, bool, str)

    def __init__(self, row, db_data):
        super().__init__()
        self.row = row
        self.db_data = db_data

    def run(self):
        db = ConnOracle(
            username=self.db_data['databaseuser'],
            password=self.db_data['databasepassword'],
            host=self.db_data['databaseip'],
            port=self.db_data['databaseport'],
            service_name=self.db_data['databasesid']
        )
        try:
            result = db.connect()
            if result == "successful":
                self.result_signal.emit(self.row, True, "")
            else:
                self.result_signal.emit(self.row, False, result)
        except Exception as e:
            self.result_signal.emit(self.row, False, str(e))
        finally:
            db.disconnect()


# ================= 主界面管理器 =================

class DataImpInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_DataImp()
        self.ui.setupUi(self)
        self.setObjectName("DataImp Interface")

        init_db_table()
        self.db_data_list = []
        self.active_testers = []
        self.selected_file_path = ""
        self.csv_headers = []
        self.current_table_cols = {}

        self.load_databases()
        self._bind_events()

    def _bind_events(self):
        self.ui.btn_add.clicked.connect(self.add_db)
        self.ui.btn_copy.clicked.connect(self.copy_db)
        self.ui.btn_edit.clicked.connect(self.edit_db)
        self.ui.btn_del.clicked.connect(self.delete_db)
        self.ui.btn_test.clicked.connect(self.test_connection)
        self.ui.search_input.textChanged.connect(self.filter_databases)

        self.ui.db_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.db_table.customContextMenuRequested.connect(self.show_context_menu)

        self.ui.btn_select_table.clicked.connect(self.open_table_selector)
        self.ui.btn_select_file.clicked.connect(self.select_data_file)
        self.ui.combo_file_type.currentIndexChanged.connect(self.reload_preview)
        self.ui.btn_gen_config.clicked.connect(self.generate_ctl_config)
        self.ui.btn_import.clicked.connect(self.execute_sqlldr)
        # 👈 绑定新增的清空按钮事件
        self.ui.btn_clear.clicked.connect(self.clear_all_inputs)
    # =============== 左侧：数据库管理逻辑 ===============
    def show_context_menu(self, pos):
        item = self.ui.db_table.itemAt(pos)
        if not item: return

        menu = RoundMenu(parent=self)
        info_action = Action(FluentIcon.INFO, "查看数据库详情")
        copy_action = Action(FluentIcon.COPY, "复制选中配置")
        edit_action = Action(FluentIcon.EDIT, "修改连接配置")
        del_action = Action(FluentIcon.DELETE, "删除此配置")

        # 👈 核心修复 3：通过 QTimer 延迟 50 毫秒后再调出弹窗，完美消除假死与死锁！
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

    def load_databases(self):
        self.ui.db_table.setRowCount(0)
        self.db_data_list.clear()
        try:
            conn = pymysql.connect(**SERVER_DB_CONFIG)
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM plsql_server")
                for i, row in enumerate(cursor.fetchall()):
                    self.ui.db_table.insertRow(i)
                    st_item = QTableWidgetItem("-")
                    st_item.setTextAlignment(Qt.AlignCenter)
                    self.ui.db_table.setItem(i, 0, st_item)
                    name_item = QTableWidgetItem(row['databasename'])
                    name_item.setToolTip(row['databasename'])
                    self.ui.db_table.setItem(i, 1, name_item)
                    self.ui.db_table.setItem(i, 2, QTableWidgetItem(row['databaseip']))
                    # 👈 提取并填充用户名
                    self.ui.db_table.setItem(i, 3, QTableWidgetItem(row['databaseuser']))
                    self.db_data_list.append(row)
            conn.close()
        except Exception as e:
            InfoBar.error('数据库连接失败', str(e), parent=self.window())

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

    def add_db(self):
        dlg = DBEditDialog(self.window())
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("""
                        INSERT INTO plsql_server (databasename, databaseip, databaseport, databasesid, databaseuser, databasepassword) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (data["databasename"], data["databaseip"], data["databaseport"], data["databasesid"],
                          data["databaseuser"], data["databasepassword"]))
                conn.commit()
                conn.close()
                self.load_databases()
            except Exception as e:
                InfoBar.error('添加失败', str(e), parent=self.window())

    def copy_db(self):
        row = self.ui.db_table.currentRow()
        if row < 0: return
        db_data = self.db_data_list[row].copy()
        db_data['databasename'] = db_data['databasename'] + " - 副本"
        dlg = DBEditDialog(self.window(), db_data)
        dlg.titleLabel.setText("复制数据库配置")
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("""
                        INSERT INTO plsql_server (databasename, databaseip, databaseport, databasesid, databaseuser, databasepassword) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (data["databasename"], data["databaseip"], data["databaseport"], data["databasesid"],
                          data["databaseuser"], data["databasepassword"]))
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
                        UPDATE plsql_server 
                        SET databasename=%s, databaseip=%s, databaseport=%s, databasesid=%s, databaseuser=%s, databasepassword=%s 
                        WHERE databaseid=%s
                    """, (data["databasename"], data["databaseip"], data["databaseport"], data["databasesid"],
                          data["databaseuser"], data["databasepassword"], db_data['databaseid']))
                conn.commit()
                conn.close()
                self.load_databases()
            except Exception as e:
                InfoBar.error('更新失败', str(e), parent=self.window())

    def delete_db(self):
        row = self.ui.db_table.currentRow()
        if row < 0: return
        db_data = self.db_data_list[row]
        w = Dialog("确认删除", f"确定删除数据库 {db_data['databasename']} 吗？", self.window())
        if w.exec():
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("DELETE FROM plsql_server WHERE databaseid=%s", (db_data['databaseid'],))
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
            user = self.ui.db_table.item(i, 3).text().lower()
            # 👈 同步增加了用户名的检索支持
            self.ui.db_table.setRowHidden(i,
                                          not ((search_text in name) or (search_text in ip) or (search_text in user)))

    # =============== 右侧：导入操作逻辑 ===============
    def open_table_selector(self):
        row = self.ui.db_table.currentRow()
        if row < 0:
            InfoBar.warning("提示", "请先在左侧选择目标数据库！", parent=self.window())
            return

        db_data = self.db_data_list[row]
        db = ConnOracle(
            username=db_data['databaseuser'],
            password=db_data['databasepassword'],
            host=db_data['databaseip'],
            port=db_data['databaseport'],
            service_name=db_data['databasesid']
        )
        db.connectorcl()

        if not db.connection or not db.cursor:
            InfoBar.error("连接数据库失败", "请检查网络、端口或账号密码是否正确", parent=self.window())
            return

        try:
            records = db.fetch_all("SELECT tname FROM tab WHERE tabtype='TABLE'")
            if records is None: return
            tables = [r[0] for r in records]
        finally:
            db.disconnect()

        if not tables:
            InfoBar.warning("提示", "该用户下没有找到任何表！", parent=self.window())
            return

        dlg = TableSelectDialog(tables, self.window())
        if dlg.exec():
            selected_table = dlg.selected_table if dlg.selected_table else (
                dlg.list_widget.currentItem().text() if dlg.list_widget.currentItem() else "")
            if selected_table:
                self.ui.line_table_name.setText(selected_table)
                self.fetch_table_columns(db_data, selected_table)

    def fetch_table_columns(self, db_data, table_name):
        db = ConnOracle(
            username=db_data['databaseuser'], password=db_data['databasepassword'],
            host=db_data['databaseip'], port=db_data['databaseport'], service_name=db_data['databasesid']
        )
        db.connectorcl()
        try:
            query = f"SELECT column_name, data_type FROM user_tab_columns WHERE table_name = '{table_name.upper()}'"
            records = db.fetch_all(query)
            if records:
                self.current_table_cols = {r[0]: r[1] for r in records}
                self.build_mapping_table()
        finally:
            db.disconnect()

    def select_data_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择数据文件", "", "数据文件 (*.csv *.txt *.dat);;所有文件 (*.*)"
        )
        if not file_path: return

        self.selected_file_path = file_path
        self.ui.btn_select_file.setText(f"...{os.path.basename(file_path)}")
        self.reload_preview()

    def reload_preview(self):
        if not self.selected_file_path or not os.path.exists(self.selected_file_path):
            return

        file_type_index = self.ui.combo_file_type.currentIndex()
        delimiter = ','
        if file_type_index == 1:
            delimiter = '\t'
        elif file_type_index == 2:
            delimiter = '|'

        self.ui.preview_table.clear()
        self.csv_headers = []

        try:
            with open(self.selected_file_path, 'r') as f:#, encoding='utf-8-sig') as f:
                reader = csv.reader(f, delimiter=delimiter)
                try:
                    self.csv_headers = next(reader)
                except StopIteration:
                    return

                self.ui.preview_table.setColumnCount(len(self.csv_headers))
                self.ui.preview_table.setHorizontalHeaderLabels(self.csv_headers)

                self.ui.preview_table.setRowCount(0)
                for i, row in enumerate(reader):
                    if i >= 10: break
                    self.ui.preview_table.insertRow(i)
                    for j, value in enumerate(row):
                        self.ui.preview_table.setItem(i, j, QTableWidgetItem(str(value)))

            self.build_mapping_table()

        except Exception as e:
            InfoBar.error('文件解析失败', f"请检查文件编码或格式: {str(e)}", parent=self.window())

    def build_mapping_table(self):
        self.ui.mapping_table.setRowCount(0)
        if not self.csv_headers: return

        db_cols = list(self.current_table_cols.keys()) if self.current_table_cols else []
        self.ui.mapping_table.setRowCount(len(self.csv_headers))

        for i, header in enumerate(self.csv_headers):
            item_csv = QTableWidgetItem(header)
            item_csv.setFlags(Qt.ItemIsEnabled)
            self.ui.mapping_table.setItem(i, 0, item_csv)

            combo_target = ComboBox()
            combo_target.addItem("")
            combo_target.addItems(db_cols)

            item_type = QTableWidgetItem("")
            item_type.setFlags(Qt.ItemIsEnabled)
            self.ui.mapping_table.setItem(i, 2, item_type)

            line_fmt = LineEdit()
            line_fmt.setPlaceholderText("可填: YYYY-MM-DD HH24:MI:SS")
            self.ui.mapping_table.setCellWidget(i, 3, line_fmt)

            header_up = header.upper().strip()
            if header_up in db_cols:
                combo_target.setCurrentText(header_up)
                dtype = self.current_table_cols.get(header_up, "")
                item_type.setText(dtype)
                if "DATE" in dtype or "TIMESTAMP" in dtype:
                    line_fmt.setText("YYYY-MM-DD HH24:MI:SS")

            def make_on_change(cb, lbl_item, fmt_input):
                def on_change(text):
                    dt = self.current_table_cols.get(text, "")
                    lbl_item.setText(dt)
                    if "DATE" in dt or "TIMESTAMP" in dt:
                        if not fmt_input.text():
                            fmt_input.setText("YYYY-MM-DD HH24:MI:SS")
                    else:
                        fmt_input.clear()

                return on_change

            combo_target.currentTextChanged.connect(make_on_change(combo_target, item_type, line_fmt))
            self.ui.mapping_table.setCellWidget(i, 1, combo_target)

    def generate_ctl_config(self):
        target_table = self.ui.line_table_name.text().strip()
        if not target_table:
            InfoBar.warning("提示", "请先通过左侧按钮选择目标表名！", parent=self.window())
            return

        if not self.selected_file_path:
            InfoBar.warning("提示", "请先选择数据文件！", parent=self.window())
            return

        file_type_index = self.ui.combo_file_type.currentIndex()
        terminated_by = "',' "
        if file_type_index == 1:
            terminated_by = "'\\t'"
        elif file_type_index == 2:
            terminated_by = "'|'"

        fields_str_list = []
        for i in range(self.ui.mapping_table.rowCount()):
            combo = self.ui.mapping_table.cellWidget(i, 1)
            tgt_col = combo.currentText()
            line_edit = self.ui.mapping_table.cellWidget(i, 3)
            date_fmt = line_edit.text().strip()

            if not tgt_col:
                safe_filler = f"CSV_FILLER_{i}"
                fields_str_list.append(f"{safe_filler} FILLER")
            else:
                if date_fmt:
                    fields_str_list.append(f'{tgt_col} DATE "{date_fmt}"')
                else:
                    fields_str_list.append(f'{tgt_col}')

        fields = ",\n    ".join(fields_str_list)
        filename=self.selected_file_path.replace("\\", "/")

        ctl_content = f"""OPTIONS (SKIP=1)
LOAD DATA
INFILE '{filename}'
APPEND
INTO TABLE {target_table}
FIELDS TERMINATED BY {terminated_by} OPTIONALLY ENCLOSED BY '"'
TRAILING NULLCOLS
(
    {fields}
)"""
        self.ui.ctl_text.setPlainText(ctl_content)
        InfoBar.success('生成成功', '已生成控制文件代码，您可在下方手动修改微调', parent=self.window())

    # ================= 👈 新增：一键清空重置逻辑 =================
    def clear_all_inputs(self):
        """ 清空右侧所有已填入和解析的缓存与 UI 内容 """
        self.selected_file_path = ""
        self.csv_headers = []
        self.current_table_cols = {}

        # 重置文本输入框与选择文件按钮
        self.ui.line_table_name.clear()
        self.ui.btn_select_file.setText("选择数据文件")

        # 彻底排空表格内部所有行与列的 Widget
        self.ui.preview_table.setRowCount(0)
        self.ui.preview_table.setColumnCount(0)
        self.ui.mapping_table.setRowCount(0)

        # 清空文本域
        self.ui.ctl_text.clear()

        InfoBar.success("已清空", "所有导入配置、字段映射及预览数据已重置", parent=self.window())
    def execute_sqlldr(self):
        row = self.ui.db_table.currentRow()
        if row < 0:
            InfoBar.warning("提示", "请在左侧选择要导入的目标数据库！", parent=self.window())
            return

        ctl_code = self.ui.ctl_text.toPlainText().strip()
        if not ctl_code:
            InfoBar.warning("提示", "请先生成并检查控制文件内容！", parent=self.window())
            return

        target_table = self.ui.line_table_name.text().strip()
        if not target_table:
            target_table = "IMPORT"

        db_data = self.db_data_list[row]

        log_dir = os.path.join(os.getcwd(), "log")
        os.makedirs(log_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        ctl_path = os.path.join(log_dir, f"{target_table}_{timestamp}.ctl")
        log_path = os.path.join(log_dir, f"{target_table}_{timestamp}.log")

        try:
            with open(ctl_path, 'w') as f:#, encoding='utf-8') as f:
                f.write(ctl_code)
        except Exception as e:
            InfoBar.error("保存配置失败", f"无法生成本地 .ctl 文件: {str(e)}", parent=self.window())
            return

        ip = db_data['databaseip']
        port = db_data['databaseport']
        sid = db_data['databasesid']
        user = db_data['databaseuser']
        pwd = db_data['databasepassword']

        dsn = f"{user}/{pwd}@{ip}:{port}/{sid}"
        if user.lower() == 'sys':
            dsn += " AS SYSDBA"
        # ⭐ 核心修复 2：构建自带客户端的绝对路径
        # 根据你代码顶部的 base_dir (即 pages 目录) 向上一级进入 ljtoolbox，再进入 core/client_1
        client_dir = base_dir.parent / "core" / "client_1"
        bin_dir = client_dir / "bin"
        sqlldr_exe = bin_dir / "sqlldr.exe"
        # 如果连项目里的 sqlldr.exe 都找不到，直接弹窗阻拦
        if not sqlldr_exe.exists():
            InfoBar.error("文件缺失", f"找不到自带的客户端: {sqlldr_exe}", parent=self.window())
            return
        cmd = [str(sqlldr_exe), f"userid={dsn}", f"control={ctl_path}", f"log={log_path}"]

        self.log_dialog = SqlldrLogDialog(self.window())
        #self.runner_thread = SqlldrRunnerThread(cmd)

        # 把 client_dir 和 bin_dir 传给线程做环境“伪装”
        self.runner_thread = SqlldrRunnerThread(cmd, str(client_dir), str(bin_dir))

        self.runner_thread.output_signal.connect(self.log_dialog.append_log)
        self.runner_thread.finished_signal.connect(self.log_dialog.on_finished)

        self.runner_thread.start()
        self.log_dialog.exec()