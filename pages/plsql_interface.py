# coding:utf-8
import os,threading
import queue

from PyQt5.QtWidgets import QWidget, QFileDialog, QTableWidgetItem, QAbstractItemView, QApplication
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from keyboard import press
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBoxBase, SubtitleLabel, LineEdit, RoundMenu, Action, \
    FluentIcon
import pymysql

from config.config import SERVER_DB_CONFIG
from ui.ui_plsql import Ui_Plsql
from core.ConnOracle import ConnOracle

class BatchEditDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(350)
        self.titleLabel = SubtitleLabel('批量修数据库凭证', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.user_input = LineEdit(self.widget)
        self.user_input.setPlaceholderText("请输入统一的新用户名")
        self.viewLayout.addWidget(self.user_input)

        self.pwd_input = LineEdit(self.widget)
        self.pwd_input.setPlaceholderText("请输入统一的新密码")
        self.pwd_input.setEchoMode(LineEdit.Password)
        self.viewLayout.addWidget(self.pwd_input)

        self.yesButton.setText('确认修改')
        self.cancelButton.setText('取消')


class PlsqlInterface(QWidget):
    # 定义信号：传递标题和内容
    notify_signal = pyqtSignal(str, str)
    # 👈 核心修改 1：初始化时接收当前登录用户信息
    # 在实际的 main_ui 中调用时，可以这样传： IncaInterface(user_info={"loginid": "当前ID", "lastname": "当前名字"}, parent=self)
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Plsql()
        self.ui.setupUi(self)
        self.setObjectName("PlsqlInterface")

        # 如果没有传入用户信息，默认提供一个测试账号防崩
        self.current_user = None#user_info or {"loginid": "18029", "lastname": "张鹏程"}
        self._is_loaded = False
        self._all_checked = False

        self.ui.tableWidget.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.ui.tableWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tableWidget.customContextMenuRequested.connect(self.show_context_menu)

        # ====== 绑定顶部按钮事件 ======
        self.ui.btn_browse.clicked.connect(self.choose_program_path)
        self.ui.btn_refresh.clicked.connect(self.refresh_data)
        #self.ui.btn_query.clicked.connect(self.search_data)

        self.ui.search_input.searchSignal.connect(self.search_data)
        self.ui.search_input.clearSignal.connect(self.refresh_data)
        #self.ui.search_input.textChanged.connect(self.on_search_text_changed)
        self.ui.search_input.textChanged.connect(self.search_data)

        self.ui.btn_add.clicked.connect(self.add_blank_row)
        self.ui.btn_edit.clicked.connect(self.edit_selected_rows)
        self.ui.btn_save.clicked.connect(self.save_all_changes)
        self.ui.btn_login.clicked.connect(self.on_login_clicked)
        self.ui.btn_copy.clicked.connect(self.copy_current_row)
        self.ui.btn_delete.clicked.connect(self.delete_rows)
        self.ui.btn_select_all.clicked.connect(self.toggle_select_all)
        self.ui.btn_batch_edit.clicked.connect(self.batch_edit_credentials)
        self.ui.btn_test.clicked.connect(self.test_conn)


        self.ui.tableWidget.horizontalHeader().sectionDoubleClicked.connect(self.toggle_password_column)
        self.ui.tableWidget.cellDoubleClicked.connect(self.on_cell_double_clicked)
        # ===== 登录队列化 =====
        self._login_queue = queue.Queue()
        self._login_worker_started = False
        self._login_worker_lock = threading.Lock()
        # 正在登录的服务器集合（防重）
        self._login_running_servers = set()
        # 队列中的服务器集合（防队列重复）
        self._login_queued_servers = set()
        # 队列和集合的锁
        self._login_state_lock = threading.Lock()
        self.server_datas = []

        self.notify_signal.connect(self._show_info_bar_on_main_thread)

    def _show_info_bar_on_main_thread(self, title, message):
        # 这个函数运行在主线程，可以安全操作 InfoBar
        InfoBar.warning(title, message, parent=self.window(), duration=2000)
    def showEvent(self, event):
        super().showEvent(event)
        if not self._is_loaded:
            self.load_data_from_db()
            self._is_loaded = True

    def get_db_connection(self):
        try:
            conn = pymysql.connect(**SERVER_DB_CONFIG)
            return conn
        except Exception as e:
            InfoBar.error('数据库连接失败', f'错误: {str(e)}', parent=self.window(), duration=4000)
            return None

    # ================= 视图渲染与刷新 =================


    def refresh_data(self):
        self.ui.search_input.clear()
        self.load_data_from_db()

    def load_data_from_db(self):
        conn = self.get_db_connection()
        if not conn: return

        server_data, exe_path = [], ""

        try:
            with conn.cursor() as cursor:
                # 👈 核心修改 2：加入 AND owner = %s 数据权限隔离
                cursor.execute("SELECT * FROM plsql_server")
                server_data = cursor.fetchall()

                # 查询程序路径不受 owner 限制
                cursor.execute("SELECT exepath FROM exe_path WHERE exetype = 'plsql'  and username= %s", (self.current_user['loginid']))
                exe_result = cursor.fetchone()
                if exe_result: exe_path = exe_result.get('exepath', '')
        except Exception as e:
            pass
        finally:
            conn.close()

        self.ui.path_input.setText(exe_path)
        self.render_table(server_data)
    def test_conn(self):
        target_rows = self.get_target_rows()
        if target_rows:
            for row in target_rows:
                row_data = []
                # 👈 列 1到5 (IP,名称,用户名,密码,类型) 的编辑权限，屏蔽所有者信息的修改！
                for col in [1, 2, 3, 4, 5, 6]:
                    item = self.ui.tableWidget.item(row, col)

                    if item is not None:
                        if col == 4:
                            current_text = item.text()
                            real_password = item.data(Qt.UserRole)
                            item.setText(real_password if current_text == "******" else real_password)
                        # 获取单元格的文本内容并添加到行数据列表
                        cell_text = item.text()
                        row_data.append(cell_text)
                    else:
                        row_data.append(None)  # 或者你可以用其他标识表示空数据
                db = ConnOracle(row_data[2], row_data[3], row_data[0], row_data[4], row_data[5])
                try:
                    connresult = db.connect()
                    item = QTableWidgetItem(str(connresult))
                    self.ui.tableWidget.setItem(row, 7, item)
                    QApplication.processEvents()  # Process events to update the UI
                finally:
                    db.disconnect()
        else:
            InfoBar.warning('提示', f'请至少选择一行', parent=self.window(), duration=4000)
    def render_table(self, data_list):
        self.ui.tableWidget.setRowCount(0)
        self._all_checked = False

        for row_idx, row_data in enumerate(data_list):
            self.ui.tableWidget.insertRow(row_idx)
            real_password = str(row_data.get('databasepassword', ''))

            view_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
            fields = [
                str(row_data.get('databaseid', '')),
                str(row_data.get('databaseip', '')),
                str(row_data.get('databasename', '')),
                str(row_data.get('databaseuser', '')),
                "******",
                str(row_data.get('databaseport', '')),
                str(row_data.get('databasesid', '')),
                "",
                ""
            ]

            for col_idx, text in enumerate(fields):
                item = QTableWidgetItem(text)
                if col_idx == 0:
                    item.setFlags(view_flags)
                    item.setCheckState(Qt.Unchecked)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                item.setTextAlignment(Qt.AlignCenter)
                if col_idx == 4: item.setData(Qt.UserRole, real_password)

                if col_idx == 8:
                    item.setForeground(QColor("#888888"))

                self.ui.tableWidget.setItem(row_idx, col_idx, item)

    def get_target_rows(self):
        rows_set = set()
        for row in range(self.ui.tableWidget.rowCount()):
            item = self.ui.tableWidget.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                rows_set.add(row)

        for item in self.ui.tableWidget.selectedItems():
            rows_set.add(item.row())

        return sorted(list(rows_set))

    # ================= 修改、复制、新增机制 =================

    def edit_selected_rows(self):
        target_rows = self.get_target_rows()
        if not target_rows:
            InfoBar.warning('提示', '请先在前方打勾或用鼠标选中需要修改的行！', parent=self.window(), duration=2000)
            return

        for row in target_rows:
            # 👈 核心修改 3：只开放列 1到5 (IP,名称,用户名,密码,类型) 的编辑权限，屏蔽所有者信息的修改！
            for col in [1, 2, 3, 4, 5, 6]:
                item = self.ui.tableWidget.item(row, col)
                if item:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)

            status_item = self.ui.tableWidget.item(row, 8)
            if status_item:
                status_item.setText("✏️ 修改中")
                status_item.setForeground(QColor("#0078D4"))

        first_row = target_rows[0]
        self.ui.tableWidget.setCurrentCell(first_row, 1)
        self.ui.tableWidget.editItem(self.ui.tableWidget.item(first_row, 1))

    def copy_current_row(self):
        target_rows = self.get_target_rows()
        if not target_rows:
            InfoBar.warning('提示', '请先打勾或鼠标选中要复制的记录！', parent=self.window(), duration=2000)
            return

        first_new_row_idx = -1
        edit_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        lock_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled  # 锁定不可修改

        for target_row in target_rows:
            last_row = self.ui.tableWidget.rowCount()
            if first_new_row_idx == -1:
                first_new_row_idx = last_row

            self.ui.tableWidget.insertRow(last_row)

            for col in range(9):
                original_item = self.ui.tableWidget.item(target_row, col)

                if col == 0:
                    item = QTableWidgetItem("")
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                elif col == 8:
                    item = QTableWidgetItem("✨ 新增")
                    item.setFlags(lock_flags)
                    item.setForeground(QColor("#107C41"))
                else:
                    text = "******" if col == 4 else (original_item.text() if original_item else "")
                    item = QTableWidgetItem(text)
                    item.setFlags(edit_flags)
                    if col == 4 and original_item:
                        item.setData(Qt.UserRole, original_item.data(Qt.UserRole))

                item.setTextAlignment(Qt.AlignCenter)
                self.ui.tableWidget.setItem(last_row, col, item)

        self.ui.tableWidget.scrollToBottom()
        if first_new_row_idx != -1:
            self.ui.tableWidget.setCurrentCell(first_new_row_idx, 1)
            self.ui.tableWidget.editItem(self.ui.tableWidget.item(first_new_row_idx, 1))

    def add_blank_row(self):
        row_idx = self.ui.tableWidget.rowCount()
        self.ui.tableWidget.insertRow(row_idx)

        id_item = QTableWidgetItem("")
        id_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        id_item.setCheckState(Qt.Unchecked)
        self.ui.tableWidget.setItem(row_idx, 0, id_item)

        edit_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        lock_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled

        for col in range(1, 9):
            if col == 8:
                text = "✨ 新增"
                item = QTableWidgetItem(text)
                item.setFlags(lock_flags)
                item.setForeground(QColor("#107C41"))
            else:
                text = ""
                item = QTableWidgetItem(text)
                item.setFlags(edit_flags)

            item.setTextAlignment(Qt.AlignCenter)
            self.ui.tableWidget.setItem(row_idx, col, item)

        self.ui.tableWidget.scrollToBottom()
        self.ui.tableWidget.setCurrentCell(row_idx, 1)
        self.ui.tableWidget.editItem(self.ui.tableWidget.item(row_idx, 1))

    # ================= 保存机制 =================

    def save_all_changes(self):
        row_count = self.ui.tableWidget.rowCount()
        insert_data = []
        update_data = []


        for row in range(row_count):
            item1 = self.ui.tableWidget.item(row, 1)
            if not item1 or not (item1.flags() & Qt.ItemIsEditable):
                continue

            id_item = self.ui.tableWidget.item(row, 0)
            row_id = id_item.text().strip() if id_item else ""

            ip = self.ui.tableWidget.item(row, 1).text().strip() if self.ui.tableWidget.item(row, 1) else ""
            name = self.ui.tableWidget.item(row, 2).text().strip() if self.ui.tableWidget.item(row, 2) else ""
            user = self.ui.tableWidget.item(row, 3).text().strip() if self.ui.tableWidget.item(row, 3) else ""
            pwd = self.ui.tableWidget.item(row, 4).text().strip() if self.ui.tableWidget.item(row, 4) else ""
            port = self.ui.tableWidget.item(row, 5).text().strip() if self.ui.tableWidget.item(row,5) else ""
            sid = self.ui.tableWidget.item(row, 6).text().strip() if self.ui.tableWidget.item(row,6) else ""

            pwd_item = self.ui.tableWidget.item(row, 4)
            if pwd_item and pwd_item.data(Qt.UserRole) and pwd == "******":
                pwd = pwd_item.data(Qt.UserRole)

            if ip or name:
                if row_id == "":
                    insert_data.append((ip, name, user, pwd, port, sid))
                else:
                    update_data.append((ip, name, user, pwd, port, sid, row_id))

        if not insert_data and not update_data:
            InfoBar.info('提示', '未检测到任何修改或新增的数据需要保存。', parent=self.window(), duration=2000)
            return

        conn = self.get_db_connection()
        if not conn: return
        try:
            with conn.cursor() as cursor:
                if insert_data:
                    sql_insert = "INSERT INTO plsql_server (databaseip, databasename, databaseuser, databasepassword, databaseport, databasesid) VALUES (%s, %s, %s, %s, %s, %s)"
                    cursor.executemany(sql_insert, insert_data)
                if update_data:
                    sql_update = "UPDATE plsql_server SET databaseip=%s, databasename=%s, databaseuser=%s, databasepassword=%s, databaseport=%s, databasesid=%s WHERE databaseid=%s"
                    cursor.executemany(sql_update, update_data)
            conn.commit()
            InfoBar.success('存盘成功', f'数据库已更新！(新增: {len(insert_data)}条，修改: {len(update_data)}条)',
                            parent=self.window(), duration=3000)
        except Exception as e:
            InfoBar.error('存盘失败', f'{str(e)}', parent=self.window(), duration=4000)
        finally:
            conn.close()

        self.load_data_from_db()

    # ================= 辅助与其他交互 =================

    def show_context_menu(self, pos):
        row = self.ui.tableWidget.rowAt(pos.y())
        if row < 0: return

        is_selected = False
        for selected_item in self.ui.tableWidget.selectedItems():
            if selected_item.row() == row:
                is_selected = True
                break

        if not is_selected:
            self.ui.tableWidget.clearSelection()
            self.ui.tableWidget.selectRow(row)
            self.ui.tableWidget.setCurrentCell(row, 0)

        menu = RoundMenu(parent=self)

        action_login = Action(FluentIcon.PEOPLE, "登录选中项")
        action_login.triggered.connect(self.on_login_clicked)

        action_copy = Action(FluentIcon.COPY, "复制选中项")
        action_copy.triggered.connect(self.copy_current_row)

        action_edit = Action(FluentIcon.EDIT, "修改选中项")
        action_edit.triggered.connect(self.edit_selected_rows)

        action_batch = Action(FluentIcon.UPDATE, "批量修改账号密码")
        action_batch.triggered.connect(self.batch_edit_credentials)

        action_delete = Action(FluentIcon.DELETE, "删除选中项")
        action_delete.triggered.connect(self.delete_rows)

        menu.addAction(action_login)
        menu.addSeparator()
        menu.addAction(action_copy)
        menu.addAction(action_edit)
        menu.addAction(action_batch)
        menu.addSeparator()
        menu.addAction(action_delete)

        menu.exec(self.ui.tableWidget.viewport().mapToGlobal(pos))

    def search_data(self, text=""):
        """ 实时模糊搜索：一边输入一边匹配 """
        # 获取当前搜索框的内容（text 参数是 textChanged 信号自动传进来的）
        keyword = self.ui.search_input.text().strip().lower()

        # 遍历所有行进行显示或隐藏
        for row in range(self.ui.tableWidget.rowCount()):
            match = False
            # 遍历该行的关键列（如IP、名称等）
            for col in [1, 2, 3]:  # 你可以根据需要调整搜索哪些列
                item = self.ui.tableWidget.item(row, col)
                if item and keyword in item.text().lower():
                    match = True
                    break

            # 如果没匹配到，隐藏该行；匹配到了则显示
            self.ui.tableWidget.setRowHidden(row, not match)

    def on_search_text_changed(self, text):
        if not text.strip():
            self.search_data()

    def toggle_password_column(self, logicalIndex):
        if logicalIndex == 4:
            for row in range(self.ui.tableWidget.rowCount()):
                item = self.ui.tableWidget.item(row, 4)
                if item and item.data(Qt.UserRole) is not None:
                    current_text = item.text()
                    real_password = item.data(Qt.UserRole)
                    item.setText(real_password if current_text == "******" else "******")

    def toggle_select_all(self):
        self._all_checked = not self._all_checked
        state = Qt.Checked if self._all_checked else Qt.Unchecked
        for row in range(self.ui.tableWidget.rowCount()):
            if not self.ui.tableWidget.isRowHidden(row):
                item = self.ui.tableWidget.item(row, 0)
                if item and item.flags() & Qt.ItemIsUserCheckable:
                    item.setCheckState(state)

    def delete_rows(self):
        target_rows = self.get_target_rows()
        if not target_rows:
            InfoBar.warning('提示', '请先打勾或选中需要删除的行！', parent=self.window(), duration=2000)
            return
        ids_to_delete = []
        for r in target_rows:
            item = self.ui.tableWidget.item(r, 0)
            if item and item.text():
                ids_to_delete.append(item.text())
        if ids_to_delete:
            conn = self.get_db_connection()
            if not conn: return
            try:
                with conn.cursor() as cursor:
                    format_strings = ','.join(['%s'] * len(ids_to_delete))
                    sql = f"DELETE FROM plsql_server WHERE databaseid IN ({format_strings})"
                    cursor.execute(sql, ids_to_delete)
                conn.commit()
                InfoBar.success('删除成功', f'已彻底移除 {len(ids_to_delete)} 条记录。', parent=self.window(),
                                duration=2000)
            except Exception as e:
                pass
            finally:
                conn.close()
        self.load_data_from_db()

    def batch_edit_credentials(self):
        target_rows = self.get_target_rows()
        if not target_rows:
            InfoBar.warning('提示', '请先选中需要批量修改账号的记录！', parent=self.window(), duration=2000)
            return
        ids_to_update = [self.ui.tableWidget.item(r, 0).text() for r in target_rows if
                         self.ui.tableWidget.item(r, 0).text()]
        if not ids_to_update:
            InfoBar.warning('提示', '选中的皆为未保存的新行。', parent=self.window(), duration=2000)
            return

        w = BatchEditDialog(self.window())
        if w.exec() and w.user_input.text().strip() and w.pwd_input.text().strip():
            new_user = w.user_input.text().strip()
            new_pwd = w.pwd_input.text().strip()
            conn = self.get_db_connection()
            if not conn: return
            try:
                with conn.cursor() as cursor:
                    format_strings = ','.join(['%s'] * len(ids_to_update))
                    sql = f"UPDATE plsql_server SET databaseuser=%s, databasepassword=%s WHERE databaseid IN ({format_strings})"
                    cursor.execute(sql, [new_user, new_pwd] + ids_to_update)
                conn.commit()
                InfoBar.success('成功', f'已批量更新 {len(ids_to_update)} 条记录！', parent=self.window(), duration=2000)
                self.load_data_from_db()
            except Exception as e:
                pass
            finally:
                conn.close()

    def choose_program_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择程序文件", "C:/",
                                                   "Executable Files (*.exe);;All Files (*)")
        if not file_path: return
        self.ui.path_input.setText(file_path)
        conn = self.get_db_connection()
        if not conn: return
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as cnt FROM exe_path WHERE exetype = 'plsql' and username= %s", (self.current_user['loginid']))
                if cursor.fetchone()['cnt'] > 0:
                    cursor.execute("UPDATE exe_path SET exepath = %s WHERE exetype = 'plsql' and username= %s", (file_path, self.current_user['loginid']))
                else:
                    cursor.execute("INSERT INTO exe_path (exetype, exepath, username) VALUES ('plsql', %s, %s)", ( file_path, self.current_user['loginid']))
            conn.commit()
        except Exception as e:
            pass
        finally:
            conn.close()

    def on_context_login(self, target_row):
        self.on_login_clicked()

    def on_cell_double_clicked(self, row, col):
        if col == 4:
            item = self.ui.tableWidget.item(row, col)
            if item and item.data(Qt.UserRole) is not None:
                current_text = item.text()
                real_password = item.data(Qt.UserRole)
                item.setText(real_password if current_text == "******" else "******")
        else:  # 排除各种非业务数据列
            exe_path = self.ui.path_input.text().strip()
            if not exe_path or not os.path.exists(exe_path):
                self.notify_signal.emit('提示', '未正确配置plsql程序路径，请选择你的plsql安装路径下的plsqldev.exe！')
                return
            item = self.ui.tableWidget.item(row, col)
            if item and not (item.flags() & Qt.ItemIsEditable):
                self.execute_login_by_row([row])

    def on_login_clicked(self):
        target_rows = self.get_target_rows()
        exe_path = self.ui.path_input.text().strip()
        if not exe_path or not os.path.exists(exe_path):
            self.notify_signal.emit('提示', '未正确配置plsql程序路径，请选择你的plsql安装路径下的plsqldev.exe！')
            return
        if target_rows:
            #for r in target_rows: self.execute_login_by_row(r)
            self.execute_login_by_row(target_rows)
            return
        InfoBar.warning('提示', '请先用鼠标选中或打勾！', parent=self.window(), duration=2000)

    def execute_login_by_row(self, rows):

        for row in rows:
            id_item = self.ui.tableWidget.item(row, 0)
            if not id_item or id_item.text() == "":
                InfoBar.warning('提示', '遇到未保存的空行，已跳过。', parent=self.window(), duration=2000)
                return
            pwd_item = self.ui.tableWidget.item(row, 4)
            password = pwd_item.data(Qt.UserRole) if pwd_item else ""
            server_data = {
                "databaseid": self.ui.tableWidget.item(row, 0).text(),
                "databaseip": self.ui.tableWidget.item(row, 1).text(),
                "databasename": self.ui.tableWidget.item(row, 2).text(),
                "databaseuser": self.ui.tableWidget.item(row, 3).text(),
                "databasepassword": password,
                "databaseport": self.ui.tableWidget.item(row, 5).text(),
                "databasesid": self.ui.tableWidget.item(row, 6).text(),
                #"ownername": self.ui.tableWidget.item(row, 7).text(),
                "exe_path": self.ui.path_input.text()
            }
            self.server_datas.append(server_data)
        self.login_to_server(self.server_datas)

    def login_to_server(self, server_datas):
        with self._login_state_lock:
            for server in server_datas:
                # 如果正在登录或已经在队列里 → 跳过
                if server["databaseid"] in self._login_running_servers or server["databaseid"] in self._login_queued_servers:
                    continue

                self._login_queue.put(server["databaseid"])
                self._login_queued_servers.add(server["databaseid"])

        self._ensure_login_worker()
        """ 开启一个新线程，执行自动登录，防止阻塞 UI """
        #threading.Thread(target=self._run_auto_login, args=(server_data,), daemon=True).start()
        # 启动队列线程
    def _ensure_login_worker(self):
        with self._login_worker_lock:
            if self._login_worker_started:
                return

            self._login_worker_started = True

            threading.Thread(
                target=self._login_worker_loop,
                daemon=True
            ).start()
    #队列工作循环
    def _login_worker_loop(self):
        while True:
            serverid = self._login_queue.get()  # 阻塞直到有任务

            # 标记为正在登录
            with self._login_state_lock:
                self._login_queued_servers.discard(serverid)
                self._login_running_servers.add(serverid)

            try:
                # 调用你原来的登录函数
                self._run_auto_login(serverid)

            except Exception as e:
                print(f'登录 {serverid} 异常:', e)

            finally:
                # 登录完成后释放
                with self._login_state_lock:
                    self._login_running_servers.discard(serverid)
                self._login_queue.task_done()

    def _run_auto_login(self, serverid):
        import psutil,pywinauto
        import win32process
        from win32gui import FindWindow, SetForegroundWindow, GetWindowRect
        from pywinauto import findwindows
        from subprocess import Popen
        server_data = next((item for item in self.server_datas if item["databaseid"] == serverid), None)
        username=server_data["databaseuser"]
        password=server_data["databasepassword"]
        dbname=server_data["databaseip"]
        try:
            windows = findwindows.find_windows(class_name='TLogOnForm')
            if windows:
                hwnd1 = windows[0]
                _, pid = win32process.GetWindowThreadProcessId(hwnd1)
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=3)

            # 找 exe 路径
            exe_path = self.ui.path_input.text().strip()
            user_id = server_data["databaseuser"]
            pwd = server_data["databasepassword"]
            if not user_id or not pwd:
                self.notify_signal.emit('提示', '未配置账号密码')
                return


            # 启动 npserver.exe
            Popen(exe_path, shell=False)

            #hwnd = None
            pywinauto.timings.wait_until_passes(20, 0.5,
                                                lambda: pywinauto.findwindows.find_windows(title=u'Oracle 登录',
                                                                                           class_name='TLogOnForm')[0])
            hwnd = FindWindow('TLogOnForm', None)
            if not hwnd:
                self.notify_signal.emit('提示', 'plsql程序已启动，但登录窗口未就绪，请稍后再试')
                return
            SetForegroundWindow(hwnd)
            app = pywinauto.Application().connect(handle=hwnd)
            dlg = app.window(handle=hwnd)
            edit_username = dlg.child_window(class_name="TEdit", found_index=1)
            edit_password = dlg.child_window(class_name="TEdit", found_index=0)
            combo_db = dlg.child_window(class_name="TComboBox", found_index=0)
            # "连接为" 下拉框 (根据你的输出，它是 title="Normal" 的 TComboBox)
            combo_connect_as = dlg.child_window(class_name="TComboBox", found_index=1)
            edit_db = combo_db.child_window(class_name="Edit", found_index=0)
            btn_ok = dlg.child_window(title="确定", class_name="TButton")
            edit_username.set_edit_text(username)
            edit_password.set_edit_text(password)
            edit_db.set_edit_text(dbname + "/orcl")
            if username.lower() == "sys":
                # 这里的 's' 会触发 Delphi 控件的加速键选择 SYSDBA
                combo_connect_as.select("SYSDBA")
            btn_ok.click()
            pywinauto.timings.wait_until_passes(2, 0.5,
                                                lambda: pywinauto.findwindows.find_windows(title=u'毁损恢复',
                                                                                           class_name='TCrashForm')[0])
            press('enter')
        except Exception as e:
            print(str(e))