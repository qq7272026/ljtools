# coding:utf-8
import os,threading
import queue

from PyQt5.QtWidgets import QWidget, QFileDialog, QTableWidgetItem, QAbstractItemView, QApplication
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from qfluentwidgets import InfoBar, InfoBarPosition, MessageBoxBase, SubtitleLabel, LineEdit, RoundMenu, Action, \
    FluentIcon
import pymysql

from config.config import SERVER_DB_CONFIG
from ui.ui_inca import Ui_Inca


class BatchEditDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(350)
        self.titleLabel = SubtitleLabel('批量修改服务器凭证', self.widget)
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


class IncaInterface(QWidget):
    # 定义信号：传递标题和内容
    notify_signal = pyqtSignal(str, str)
    # 👈 核心修改 1：初始化时接收当前登录用户信息
    # 在实际的 main_ui 中调用时，可以这样传： IncaInterface(user_info={"loginid": "当前ID", "lastname": "当前名字"}, parent=self)
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Inca()
        self.ui.setupUi(self)
        self.setObjectName("IncaInterface")

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

        self.ui.radio_erpnew.toggled.connect(lambda checked: self.on_radio_toggled(checked))
        self.ui.radio_erpold.toggled.connect(lambda checked: self.on_radio_toggled(checked))
        self.ui.radio_wms.toggled.connect(lambda checked: self.on_radio_toggled(checked))

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
            self.ui.radio_erpnew.setChecked(True)
            self.load_data_from_db()
            self._is_loaded = True

    def get_db_connection(self):
        try:
            conn = pymysql.connect(**SERVER_DB_CONFIG)
            return conn
        except Exception as e:
            InfoBar.error('数据库连接失败', f'错误: {str(e)}', parent=self.window(), duration=4000)
            return None

    def get_current_type_string(self):
        if self.ui.radio_erpnew.isChecked():
            return 'erpnew'
        elif self.ui.radio_erpold.isChecked():
            return 'erpold'
        elif self.ui.radio_wms.isChecked():
            return 'wms'
        return 'erpnew'

    # ================= 视图渲染与刷新 =================

    def on_radio_toggled(self, is_checked):
        if is_checked and self._is_loaded:
            self.refresh_data()

    def refresh_data(self):
        self.ui.search_input.clear()
        self.load_data_from_db()

    def load_data_from_db(self):
        conn = self.get_db_connection()
        if not conn: return

        server_type = self.get_current_type_string()
        server_data, exe_path = [], ""

        try:
            with conn.cursor() as cursor:
                # 👈 核心修改 2：加入 AND owner = %s 数据权限隔离
                cursor.execute("SELECT * FROM inca_server WHERE servertype = %s AND owner = %s",
                               (server_type, self.current_user['loginid']))
                server_data = cursor.fetchall()

                # 查询程序路径不受 owner 限制
                cursor.execute("SELECT exepath FROM exe_path WHERE exetype = %s and username= %s", (server_type,self.current_user['loginid']))
                exe_result = cursor.fetchone()
                if exe_result: exe_path = exe_result.get('exepath', '')
        except Exception as e:
            pass
        finally:
            conn.close()

        self.ui.path_input.setText(exe_path)
        self.render_table(server_data)

    def render_table(self, data_list):
        self.ui.tableWidget.setRowCount(0)
        self._all_checked = False

        for row_idx, row_data in enumerate(data_list):
            self.ui.tableWidget.insertRow(row_idx)
            real_password = str(row_data.get('passwd', ''))

            view_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
            fields = [
                str(row_data.get('id', '')),
                str(row_data.get('serverip', '')),
                str(row_data.get('servername', '')),
                str(row_data.get('username', '')),
                "******",
                str(row_data.get('servertype', '')),
                str(row_data.get('owner', '')),
                str(row_data.get('ownername', '')),
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
            for col in [1, 2, 3, 4, 5]:
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
                elif col == 6:  # 👈 核心修改 4：复制时强制盖章当前登录人
                    item = QTableWidgetItem(self.current_user['loginid'])
                    item.setFlags(lock_flags)
                elif col == 7:  # 复制时强制盖章当前登录人名字
                    item = QTableWidgetItem(self.current_user['lastname'])
                    item.setFlags(lock_flags)
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
        current_type = self.get_current_type_string()

        for col in range(1, 9):
            if col == 5:
                text = current_type
                item = QTableWidgetItem(text)
                item.setFlags(edit_flags)
            elif col == 6:  # 👈 核心修改 5：新增时自动填充当前用户
                text = self.current_user['loginid']
                item = QTableWidgetItem(text)
                item.setFlags(lock_flags)
            elif col == 7:
                text = self.current_user['lastname']
                item = QTableWidgetItem(text)
                item.setFlags(lock_flags)
            elif col == 8:
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

        # 👈 核心修改 6：直接从上下文内存中取所有者，确保安全且杜绝被篡改
        safe_owner = self.current_user['loginid']
        safe_ownername = self.current_user['lastname']

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
            stype = self.ui.tableWidget.item(row, 5).text().strip() if self.ui.tableWidget.item(row,
                                                                                                5) else self.get_current_type_string()

            pwd_item = self.ui.tableWidget.item(row, 4)
            if pwd_item and pwd_item.data(Qt.UserRole) and pwd == "******":
                pwd = pwd_item.data(Qt.UserRole)

            if ip or name:
                if row_id == "":
                    # 组装数据，强制使用 safe_owner
                    insert_data.append((ip, name, user, pwd, stype, safe_owner, safe_ownername))
                else:
                    # 组装数据，强制更新使用 safe_owner（就算编辑了也会被覆盖回来）
                    update_data.append((ip, name, user, pwd, stype, safe_owner, safe_ownername, row_id))

        if not insert_data and not update_data:
            InfoBar.info('提示', '未检测到任何修改或新增的数据需要保存。', parent=self.window(), duration=2000)
            return

        conn = self.get_db_connection()
        if not conn: return
        try:
            with conn.cursor() as cursor:
                if insert_data:
                    sql_insert = "INSERT INTO inca_server (serverip, servername, username, passwd, servertype, owner, ownername) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                    cursor.executemany(sql_insert, insert_data)
                if update_data:
                    sql_update = "UPDATE inca_server SET serverip=%s, servername=%s, username=%s, passwd=%s, servertype=%s, owner=%s, ownername=%s WHERE id=%s"
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
            for col in [1, 2, 3, 5, 7]:  # 你可以根据需要调整搜索哪些列
                item = self.ui.tableWidget.item(row, col)
                if item and keyword in item.text().lower():
                    match = True
                    break

            # 如果没匹配到，隐藏该行；匹配到了则显示
            self.ui.tableWidget.setRowHidden(row, not match)
        # keyword = self.ui.search_input.text().strip().lower()
        # for row in range(self.ui.tableWidget.rowCount()):
        #     if not keyword:
        #         self.ui.tableWidget.setRowHidden(row, False)
        #         continue
        #
        #     match = False
        #     for col in range(1, 8):
        #         if col == 4: continue
        #         item = self.ui.tableWidget.item(row, col)
        #         if item and keyword in item.text().lower():
        #             match = True
        #             break
        #     self.ui.tableWidget.setRowHidden(row, not match)

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
                    sql = f"DELETE FROM inca_server WHERE id IN ({format_strings})"
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
                    sql = f"UPDATE inca_server SET username=%s, passwd=%s WHERE id IN ({format_strings})"
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
        server_type = self.get_current_type_string()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as cnt FROM exe_path WHERE exetype = %s and username= %s", (server_type,self.current_user['loginid']))
                if cursor.fetchone()['cnt'] > 0:
                    cursor.execute("UPDATE exe_path SET exepath = %s WHERE exetype = %s and username= %s", (file_path, server_type,self.current_user['loginid']))
                else:
                    cursor.execute("INSERT INTO exe_path (exetype, exepath, username) VALUES (%s, %s, %s)", (server_type, file_path, self.current_user['loginid']))
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
                InfoBar.error('配置错误', '未正确配置 npserver.exe 路径，请先选择程序路径！', parent=self.window(),
                              duration=3000)
                return
            item = self.ui.tableWidget.item(row, col)
            if item and not (item.flags() & Qt.ItemIsEditable):
                self.execute_login_by_row([row])

    def on_login_clicked(self):
        target_rows = self.get_target_rows()
        exe_path = self.ui.path_input.text().strip()
        if not exe_path or not os.path.exists(exe_path):
            InfoBar.error('配置错误', '未正确配置 npserver.exe 路径，请先选择程序路径！', parent=self.window(), duration=3000)
            return
        if target_rows:
            #for r in target_rows: self.execute_login_by_row(r)
            self.execute_login_by_row(target_rows)
            return
        InfoBar.warning('提示', '请先用鼠标选中或打勾！', parent=self.window(), duration=2000)
        # 【核心修正】在启动线程前，先在主线程进行一次统一的配置校验

    def execute_login_by_row(self, rows):
        # 👈 修复 1：创建一个属于“本次点击”的局部列表，不让历史记录堆积
        current_login_list = []

        for row in rows:
            id_item = self.ui.tableWidget.item(row, 0)
            if not id_item or id_item.text() == "":
                InfoBar.warning('提示', '遇到未保存的空行，已跳过。', parent=self.window(), duration=2000)
                return
            pwd_item = self.ui.tableWidget.item(row, 4)
            password = pwd_item.data(Qt.UserRole) if pwd_item else ""
            server_data = {
                "id": self.ui.tableWidget.item(row, 0).text(),
                "serverip": self.ui.tableWidget.item(row, 1).text(),
                "servername": self.ui.tableWidget.item(row, 2).text(),
                "username": self.ui.tableWidget.item(row, 3).text(),
                "passwd": password,
                "servertype": self.ui.tableWidget.item(row, 5).text(),
                "owner": self.ui.tableWidget.item(row, 6).text(),
                "ownername": self.ui.tableWidget.item(row, 7).text(),
                "exe_path": self.ui.path_input.text()
            }

            # 👈 修复 2：更新全局列表（给后台线程查账号密码用），但用替换代替追加，防止重复
            existing_idx = next((i for i, item in enumerate(self.server_datas) if item["id"] == server_data["id"]), -1)
            if existing_idx != -1:
                self.server_datas[existing_idx] = server_data  # 如果有了，就覆盖更新它
            else:
                self.server_datas.append(server_data)  # 只有第一次遇到的新 ID 才追加

            # 把当前选中的放进本次登录列表
            current_login_list.append(server_data)

        # 👈 修复 3：只把“本次选中的这几条”塞进登录队列！
        self.login_to_server(current_login_list)

    def login_to_server(self, server_datas):
        with self._login_state_lock:
            for server in server_datas:
                # 如果正在登录或已经在队列里 → 跳过
                if server["id"] in self._login_running_servers or server["id"] in self._login_queued_servers:
                    continue

                self._login_queue.put(server["id"])
                self._login_queued_servers.add(server["id"])

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
        import psutil
        import win32process,win32clipboard
        from win32api import SetCursorPos, mouse_event
        from win32con import MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,CF_UNICODETEXT
        from win32gui import FindWindow, SetForegroundWindow, GetWindowRect
        from pyautogui import hotkey, press, typewrite
        from pywinauto import findwindows,keyboard
        from subprocess import Popen
        from time import sleep
        server_data = next((item for item in self.server_datas if item["id"] == serverid), None)
        try:
            windows = findwindows.find_windows(class_name='SunAwtDialog')
            if windows:
                hwnd1 = windows[0]
                _, pid = win32process.GetWindowThreadProcessId(hwnd1)
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=3)
            ip = server_data["serverip"]

            # 找 exe 路径
            exe_path = server_data["exe_path"]

            user_id = server_data["username"]
            pwd = server_data["passwd"]
            if not user_id or not pwd:
                self.notify_signal.emit('提示', '未配置账号密码')
                return

            # ============= 清理日志文件 =============
            logdir = exe_path.replace('npserver.exe', 'logs/')
            self._cleanup_logs(logdir)

            # 启动 npserver.exe
            Popen(exe_path, shell=False)

            hwnd1 = None
            for i in range(30):  # 最多等 15 秒
                try:
                    windows = findwindows.find_windows(class_name='SunAwtDialog')
                    if windows:
                        hwnd1 = windows[0]
                        break
                except:
                    pass
                sleep(0.5)

            if not hwnd1:
                self.notify_signal.emit('提示', '英克程序已启动，但登录窗口未就绪，请稍后再试')
                return

            # ============= 快速查找窗口 =============
            hwnd1 = None
            max_attempts = 10
            found = False

            for i in range(max_attempts):
                try:
                    windows = findwindows.find_windows(class_name='SunAwtDialog')
                    if windows:
                        hwnd1 = windows[0]
                        print(f"找到SunAwtDialog窗口，句柄: {hwnd1}")
                        found = True
                        break

                    hwnd1 = FindWindow('SunAwtDialog', None)
                    if hwnd1:
                        print(f"使用FindWindow找到窗口，句柄: {hwnd1}")
                        found = True
                        break

                    sleep(0.5)
                    print(f"第{i + 1}次尝试查找英克窗口...")

                except Exception as e:
                    print(f"查找窗口时出错: {e}")
                    sleep(0.5)

            if not found:
                self.notify_signal.emit('提示', '英克程序已启动，但未检测到登录窗口。\n请稍后手动操作')
                return

            SetForegroundWindow(hwnd1)
            sleep(0.5)

            left, top, right, bottom = GetWindowRect(hwnd1)
            print(f"窗口坐标: left={left}, top={top}, right={right}, bottom={bottom}")

            SetCursorPos([left + 325, bottom - 175])
            sleep(0.05)
            mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            hotkey('shiftleft', 'tab')
            sleep(0.5)
            hotkey('ctrlleft', 'a')
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                # CF_UNICODETEXT 确保字符串编码正确，完美兼容中英文和特殊符号
                win32clipboard.SetClipboardData(CF_UNICODETEXT, ip)
                win32clipboard.CloseClipboard()
            except Exception as clip_e:
                print(f"写入剪贴板失败: {clip_e}")

                # 模拟物理粘贴
            keyboard.send_keys('^v')
            sleep(0.1)  # 稍微给系统一点反应时间
            #typewrite(ip)
            press('enter')
            typewrite(user_id)
            press('enter')
            hotkey('ctrlleft', 'a')
            typewrite(pwd)
            typewrite(['enter'] * 4, '0.01')
            sleep(0.5)
            press('enter')
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            self.notify_signal.emit('错误', f'自动登录失败: {error_msg}！')


    def _cleanup_logs(self, logdir):
        import re
        from pathlib import Path
        """ 清理日志的辅助方法 """
        log_path = Path(logdir)
        if not log_path.exists(): return
        date_pattern = re.compile(r'\.log\.\d{4}-\d{2}-\d{2}$')
        for file_path in log_path.iterdir():
            if file_path.is_file():
                if date_pattern.search(file_path.name):
                    file_path.unlink()
                elif file_path.name.endswith('.log'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('')