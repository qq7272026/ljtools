# pages/linux_interface.py
# coding:utf-8
import os
import re
import threading
import subprocess
import pymysql
import paramiko
from PyQt5.QtCore import Qt, QThread, pyqtSignal, qInstallMessageHandler, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QColor
from PyQt5.QtWidgets import (QWidget, QPlainTextEdit, QVBoxLayout, QTableWidgetItem,
                             QFileDialog, QHBoxLayout, QApplication, QHeaderView, QAbstractItemView)
from qfluentwidgets import (InfoBar, MessageBoxBase, SubtitleLabel, LineEdit, Dialog,
                            RoundMenu, Action, FluentIcon, PushButton, TableWidget)
from config.config import SERVER_DB_CONFIG
from ui.ui_linux import Ui_Linux
# ================= 核心修复：兼容老旧系统 (Oracle Linux 6 / CentOS 6) =================
# 1. 强行将旧版 KEX (密钥交换算法) 塞回 paramiko 的首选支持列表中
if 'diffie-hellman-group1-sha1' not in paramiko.Transport._preferred_kex:
    paramiko.Transport._preferred_kex = (
        'diffie-hellman-group14-sha1',
        'diffie-hellman-group-exchange-sha1',
        'diffie-hellman-group1-sha1',
    ) + paramiko.Transport._preferred_kex

# 2. 强行将旧版的 RSA 认证算法也加回来 (防止后续报 ssh-rsa 错误)
if 'ssh-rsa' not in paramiko.Transport._preferred_keys:
    paramiko.Transport._preferred_keys = (
        'ssh-rsa',
        'ssh-dss',
    ) + paramiko.Transport._preferred_keys
# ====================================================================================
# 定义一个 Qt 消息拦截器
def qt_message_handler(mode, context, message):
    # 只要包含这句废话，直接丢弃，不打印
    if "does not have a property named" in message:
        return
    # 其他真实的报错依然正常打印
    print(message)

# 安装拦截器
qInstallMessageHandler(qt_message_handler)


def init_linux_table():
    try:
        conn = pymysql.connect(**SERVER_DB_CONFIG)
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS linux_server (
                    serverid INT AUTO_INCREMENT PRIMARY KEY,
                    servername VARCHAR(100),
                    serverip VARCHAR(50),
                    serverport INT DEFAULT 22,
                    serveruser VARCHAR(50),
                    serverpassword VARCHAR(100),
                    serverresult VARCHAR(255)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS exe_path (
                    exetype VARCHAR(50),
                    exepath VARCHAR(255),
                    username VARCHAR(255)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"初始化表失败: {e}")


# ================= 弹窗对话框区域 =================

class ServerInfoDialog(MessageBoxBase):
    """ 👈 核心升级：纯净表格展示服务器信息，支持任意单元格复制 """

    def __init__(self, server_list, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(700)
        self.widget.setMinimumHeight(400)

        self.titleLabel = SubtitleLabel('服务器详情 (支持右键或 Ctrl+C 复制)', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        # 实例化表格
        self.table = TableWidget(self.widget)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['主机名称', 'IP 地址', '端口', '账号', '密码'])
        self.table.verticalHeader().hide()

        # 表格自适应策略
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # IP 自适应
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)  # 密码拉满

        # 允许选中单个或多个单元格，禁止双击编辑
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
        # 填充数据
        self.table.setRowCount(len(server_list))
        for i, data in enumerate(server_list):
            self.table.setItem(i, 0, QTableWidgetItem(str(data.get('servername', ''))))
            self.table.setItem(i, 1, QTableWidgetItem(str(data.get('serverip', ''))))
            self.table.setItem(i, 2, QTableWidgetItem(str(data.get('serverport', ''))))
            self.table.setItem(i, 3, QTableWidgetItem(str(data.get('serveruser', ''))))
            self.table.setItem(i, 4, QTableWidgetItem(str(data.get('serverpassword', ''))))

        # 开启右键菜单
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
        """ 劫持键盘事件，实现原生的 Ctrl+C """
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            self.copy_selected()
        else:
            super().keyPressEvent(event)

    def copy_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items: return

        # 处理可能的多行多列框选
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


class WinscpConfigDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(400)
        self.titleLabel = SubtitleLabel('配置 WinSCP 路径', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.path_layout = QHBoxLayout()
        self.path_input = LineEdit(self.widget)
        self.path_input.setPlaceholderText("请选择本地的 WinSCP.exe 绝对路径")

        self.btn_browse = PushButton("浏览...", self.widget)
        self.btn_browse.clicked.connect(self.browse_file)

        self.path_layout.addWidget(self.path_input)
        self.path_layout.addWidget(self.btn_browse)
        self.viewLayout.addLayout(self.path_layout)

        self.yesButton.setText('保存配置')
        self.cancelButton.setText('取消')

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 WinSCP 程序", "C:/", "Executable Files (*.exe)")
        if path:
            self.path_input.setText(path)


class ServerEditDialog(MessageBoxBase):
    def __init__(self, parent=None, server_data=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(350)
        self.titleLabel = SubtitleLabel('SSH 主机配置', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.name_input = LineEdit(self.widget)
        self.name_input.setPlaceholderText("显示名称 (例如: 生产 Web01)")
        self.viewLayout.addWidget(self.name_input)

        self.ip_input = LineEdit(self.widget)
        self.ip_input.setPlaceholderText("IP 地址")
        self.viewLayout.addWidget(self.ip_input)

        self.port_input = LineEdit(self.widget)
        self.port_input.setPlaceholderText("端口 (默认 22)")
        self.port_input.setText("22")
        self.viewLayout.addWidget(self.port_input)

        self.user_input = LineEdit(self.widget)
        self.user_input.setPlaceholderText("用户名 (例如: root)")
        self.viewLayout.addWidget(self.user_input)

        self.pwd_input = LineEdit(self.widget)
        self.pwd_input.setPlaceholderText("密码")
        self.pwd_input.setEchoMode(LineEdit.Password)
        self.viewLayout.addWidget(self.pwd_input)

        self.remark_input = LineEdit(self.widget)
        self.remark_input.setPlaceholderText("备注说明 (可选)")
        self.viewLayout.addWidget(self.remark_input)

        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')

        if server_data:
            self.name_input.setText(server_data.get("servername", ""))
            self.ip_input.setText(server_data.get("serverip", ""))
            self.port_input.setText(str(server_data.get("serverport", 22)))
            self.user_input.setText(server_data.get("serveruser", ""))
            self.pwd_input.setText(server_data.get("serverpassword", ""))
            self.remark_input.setText(server_data.get("serverresult", ""))

    def get_data(self):
        return {
            "servername": self.name_input.text().strip(),
            "serverip": self.ip_input.text().strip(),
            "serverport": int(self.port_input.text().strip() or 22),
            "serveruser": self.user_input.text().strip(),
            "serverpassword": self.pwd_input.text().strip(),
            "serverresult": self.remark_input.text().strip()
        }


# ================= 异步线程区域 =================

class ConnectionTesterThread(QThread):
    result_signal = pyqtSignal(int, bool, str)

    def __init__(self, row, server_data):
        super().__init__()
        self.row = row
        self.server_data = server_data

    def run(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.server_data['serverip'],
                port=self.server_data['serverport'],
                username=self.server_data['serveruser'],
                password=self.server_data['serverpassword'],
                timeout=3
            )
            client.close()
            self.result_signal.emit(self.row, True, "")
        except Exception as e:
            self.result_signal.emit(self.row, False, str(e))


class SSHReceiverThread(QThread):
    data_received = pyqtSignal(str)

    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.running = True

    def run(self):
        while self.running:
            if self.channel and self.channel.recv_ready():
                try:
                    data = self.channel.recv(4096).decode('utf-8', errors='ignore')
                    self.data_received.emit(data)
                except:
                    break
            QThread.msleep(50)

    def stop(self):
        self.running = False


class SSHTerminalWidget(QPlainTextEdit):
    print_signal = pyqtSignal(str)

    ANSI_COLORS = {
        '30': '#000000', '31': '#CD3131', '32': '#0DBC79', '33': '#E5E510',
        '34': '#2472C8', '35': '#BC3FBC', '36': '#11A8CD', '37': '#E5E5E5',
        '40': '#000000', '41': '#CD3131', '42': '#0DBC79', '43': '#E5E510',
        '44': '#2472C8', '45': '#BC3FBC', '46': '#11A8CD', '47': '#E5E5E5',
        '90': '#666666', '91': '#F14C4C', '92': '#23D18B', '93': '#F5F543',
        '94': '#3B8EEA', '95': '#D670D6', '96': '#29B8DB', '97': '#FFFFFF'
    }

    def __init__(self, server_data, parent=None):
        super().__init__(parent)
        self.server_data = server_data
        self.client = None
        self.channel = None
        self.receiver = None

        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                border: none;
                padding: 10px;
            }
        """)
        self.setCursorWidth(8)
        self.print_signal.connect(self.display_data)

        threading.Thread(target=self.connect_ssh, daemon=True).start()

    def connect_ssh(self):
        self.print_signal.emit(
            f"[*] 正在连接到 {self.server_data['serverip']}:{self.server_data['serverport']} ...\r\n")
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.server_data['serverip'],
                port=self.server_data['serverport'],
                username=self.server_data['serveruser'],
                password=self.server_data['serverpassword'],
                timeout=10
            )
            self.channel = self.client.invoke_shell(term='xterm-256color', width=120, height=40)

            self.receiver = SSHReceiverThread(self.channel)
            self.receiver.data_received.connect(self.display_data)
            self.receiver.start()
        except Exception as e:
            self.print_signal.emit(f"[-] 连接失败: {str(e)}\r\n")

    def display_data(self, data):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)

        # 过滤掉终端改名等无效控制码
        data = re.sub(r'\x1b\].*?(?:\x07|\x1b\\)', '', data)
        pattern = re.compile(r'\x1b\[([0-9;]*)m')
        last_end = 0

        # ⭐ 核心修复 1：将颜色追踪器与物理游标彻底剥离，防止换行时游标被“意外染色”
        active_fmt = cursor.charFormat()

        def insert_clean(text):
            # 将清除行指令转为内部特殊单字符，防止被当成乱码过滤
            text = re.sub(r'\x1b\[[0]?K', '\x01', text)  # 清除到行尾
            text = re.sub(r'\x1b\[2K', '\x02', text)  # 清除整行
            clean_text = re.sub(r'\x1b\[[0-9;?]*[a-ln-zA-Z]', '', text)

            # ⭐ 核心修复 2：高性能文本缓冲覆盖器，完美还原真实的终端打字效果
            buffer = []

            def flush_buffer():
                if buffer:
                    s = ''.join(buffer)
                    # 模拟覆盖模式：动态计算需要覆盖的字符数量，防止吞噬换行符
                    chars_to_del = min(len(s), cursor.block().length() - cursor.positionInBlock() - 1)
                    if chars_to_del > 0:
                        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, chars_to_del)
                        cursor.removeSelectedText()
                    cursor.setCharFormat(active_fmt)  # 严格应用当前独立锁定的颜色
                    cursor.insertText(s)
                    buffer.clear()

            for char in clean_text:
                if char in ('\x08', '\r', '\n', '\x01', '\x02', '\x07'):
                    flush_buffer()  # 遇到控制符先清空缓冲

                    if char == '\x08':  # 退格：仅左移游标，不粗暴删字
                        if not cursor.atBlockStart():
                            cursor.movePosition(QTextCursor.Left)
                    elif char == '\r':  # 回车：游标回到行首，准备覆盖
                        cursor.movePosition(QTextCursor.StartOfLine)
                    elif char == '\n':  # 换行：严格锁定颜色后写入，防止下一行被污染
                        cursor.movePosition(QTextCursor.EndOfLine)
                        cursor.setCharFormat(active_fmt)
                        cursor.insertText('\n')
                    elif char == '\x01':  # 擦除游标到行尾 (完美解决 SQL> 重叠问题)
                        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                    elif char == '\x02':  # 擦除整行
                        cursor.movePosition(QTextCursor.StartOfLine)
                        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                else:
                    buffer.append(char)
            flush_buffer()

        # 解析 ANSI 颜色代码并动态赋值给 active_fmt
        for match in pattern.finditer(data):
            text = data[last_end:match.start()]
            if text:
                insert_clean(text)

            codes = match.group(1).split(';')
            for code in codes:
                if code in ('0', '00', ''):
                    active_fmt.setForeground(QColor('#CCCCCC'))
                    active_fmt.setBackground(QColor('#1E1E1E'))
                    active_fmt.setFontWeight(QFont.Normal)
                elif code in ('1', '01'):
                    active_fmt.setFontWeight(QFont.Bold)
                elif code.startswith('3') or code.startswith('9'):
                    if code in self.ANSI_COLORS:
                        active_fmt.setForeground(QColor(self.ANSI_COLORS[code]))
                elif code.startswith('4'):
                    if code in self.ANSI_COLORS:
                        active_fmt.setBackground(QColor(self.ANSI_COLORS[code]))

            last_end = match.end()

        # 处理未被颜色代码包裹的剩余文本
        if last_end < len(data):
            insert_clean(data[last_end:])

        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def keyPressEvent(self, event):
        if not self.channel: return
        text = event.text()
        key = event.key()
        modifiers = event.modifiers()

        try:
            if modifiers & Qt.ControlModifier:
                if key == Qt.Key_C:
                    self.channel.send('\x03')
                elif key == Qt.Key_D:
                    self.channel.send('\x04')
                elif key == Qt.Key_Z:
                    self.channel.send('\x1a')
                elif key == Qt.Key_L:
                    self.channel.send('\x0c')
                event.accept()
                return

            if key == Qt.Key_Return or key == Qt.Key_Enter:
                self.channel.send('\r')
            elif key == Qt.Key_Backspace:
                self.channel.send('\x7f')
            elif key == Qt.Key_Tab:
                self.channel.send('\t')
            elif key == Qt.Key_Escape:
                self.channel.send('\x1b')
            elif key == Qt.Key_Up:
                self.channel.send('\x1b[A')
            elif key == Qt.Key_Down:
                self.channel.send('\x1b[B')
            elif key == Qt.Key_Right:
                self.channel.send('\x1b[C')
            elif key == Qt.Key_Left:
                self.channel.send('\x1b[D')
            elif text:
                self.channel.send(text)
        except:
            pass

        event.accept()

    def closeEvent(self, event):
        if self.receiver: self.receiver.stop()
        if self.client: self.client.close()
        super().closeEvent(event)


# ================= 主界面管理器 =================
class LinuxInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Linux()
        self.ui.setupUi(self)
        self.setObjectName("Linux Interface")

        init_linux_table()
        self.server_data_list = []
        self.opened_sessions = {}
        self.active_testers = []

        self.load_servers()
        self._bind_events()

        self.current_user = None
    def _bind_events(self):
        self.ui.btn_add.clicked.connect(self.add_server)
        self.ui.btn_copy.clicked.connect(self.copy_server)
        self.ui.btn_edit.clicked.connect(self.edit_server)
        self.ui.btn_del.clicked.connect(self.delete_server)
        self.ui.btn_test.clicked.connect(self.test_connection)

        self.ui.search_input.textChanged.connect(self.filter_servers)
        self.ui.server_table.itemDoubleClicked.connect(self.open_terminal)
        self.ui.tabs.tabCloseRequested.connect(self.close_tab)

        self.ui.server_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.server_table.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        item = self.ui.server_table.itemAt(pos)
        if not item:
            return

        menu = RoundMenu(parent=self)

        info_action = Action(FluentIcon.INFO, "查看服务器详情")
        winscp_action = Action(FluentIcon.FOLDER, "打开 WinSCP 文件管理")
        copy_action = Action(FluentIcon.COPY, "复制选中主机")
        edit_action = Action(FluentIcon.EDIT, "修改连接配置")
        del_action = Action(FluentIcon.DELETE, "删除此主机")

        # 👈 核心修复 3：通过 QTimer 延迟 50 毫秒后再调出弹窗，完美消除假死与死锁！
        info_action.triggered.connect(lambda: QTimer.singleShot(50, self.view_server_info))
        winscp_action.triggered.connect(lambda: QTimer.singleShot(50, self.open_winscp))
        copy_action.triggered.connect(lambda: QTimer.singleShot(50, self.copy_server))
        edit_action.triggered.connect(lambda: QTimer.singleShot(50, self.edit_server))
        del_action.triggered.connect(lambda: QTimer.singleShot(50, self.delete_server))

        menu.addAction(info_action)
        menu.addAction(winscp_action)
        menu.addSeparator()
        menu.addAction(copy_action)
        menu.addAction(edit_action)
        menu.addSeparator()
        menu.addAction(del_action)

        menu.exec(self.ui.server_table.mapToGlobal(pos))

    def view_server_info(self):
        """ 👈 将选中的主机数据以数组的形式发给新的表格弹窗 """
        selected_rows = self.ui.server_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        selected_data = []
        for model_index in selected_rows:
            row = model_index.row()
            if self.ui.server_table.isRowHidden(row):
                continue
            selected_data.append(self.server_data_list[row])

        if not selected_data:
            return

        dlg = ServerInfoDialog(selected_data, self.window())
        dlg.exec()

    def load_servers(self):
        self.ui.server_table.setRowCount(0)
        self.server_data_list.clear()
        try:
            conn = pymysql.connect(**SERVER_DB_CONFIG)
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM linux_server")
                for i, row in enumerate(cursor.fetchall()):
                    self.ui.server_table.insertRow(i)

                    st_item = QTableWidgetItem("-")
                    st_item.setTextAlignment(Qt.AlignCenter)
                    self.ui.server_table.setItem(i, 0, st_item)

                    name_item = QTableWidgetItem(row['servername'])
                    name_item.setToolTip(row['servername'])
                    self.ui.server_table.setItem(i, 1, name_item)

                    self.ui.server_table.setItem(i, 2, QTableWidgetItem(row['serverip']))

                    self.server_data_list.append(row)
            conn.close()
        except Exception as e:
            InfoBar.error('数据库连接失败', str(e), parent=self.window())

    def test_connection(self):
        selected_rows = self.ui.server_table.selectionModel().selectedRows()
        if not selected_rows:
            InfoBar.warning("提示", "请先在列表中选中要测试的主机", parent=self.window())
            return

        for i in range(self.ui.server_table.rowCount()):
            item = QTableWidgetItem("-")
            item.setTextAlignment(Qt.AlignCenter)
            self.ui.server_table.setItem(i, 0, item)

        for model_index in selected_rows:
            row = model_index.row()
            if self.ui.server_table.isRowHidden(row):
                continue

            wait_item = QTableWidgetItem("⏳")
            wait_item.setTextAlignment(Qt.AlignCenter)
            self.ui.server_table.setItem(row, 0, wait_item)

            server_data = self.server_data_list[row]
            tester = ConnectionTesterThread(row, server_data)
            tester.result_signal.connect(self.on_test_result)
            tester.start()
            self.active_testers.append(tester)

    def on_test_result(self, row, success, error_msg):
        res_item = QTableWidgetItem("✅" if success else "❌")
        res_item.setTextAlignment(Qt.AlignCenter)
        if not success:
            res_item.setToolTip(f"连接失败: {error_msg}")
        self.ui.server_table.setItem(row, 0, res_item)

    def add_server(self):
        dlg = ServerEditDialog(self.window())
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("""
                        INSERT INTO linux_server (servername, serverip, serverport, serveruser, serverpassword, serverresult) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (data["servername"], data["serverip"], data["serverport"], data["serveruser"],
                          data["serverpassword"], data["serverresult"]))
                conn.commit()
                conn.close()
                self.load_servers()
            except Exception as e:
                InfoBar.error('添加失败', str(e), parent=self.window())

    def copy_server(self):
        row = self.ui.server_table.currentRow()
        if row < 0:
            InfoBar.warning("提示", "请先在列表中选中一台要复制的主机", parent=self.window())
            return

        server_data = self.server_data_list[row].copy()
        server_data['servername'] = server_data['servername'] + " - 副本"

        dlg = ServerEditDialog(self.window(), server_data)
        dlg.titleLabel.setText("复制 SSH 主机配置")

        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("""
                        INSERT INTO linux_server (servername, serverip, serverport, serveruser, serverpassword, serverresult) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (data["servername"], data["serverip"], data["serverport"], data["serveruser"],
                          data["serverpassword"], data["serverresult"]))
                conn.commit()
                conn.close()
                InfoBar.success('成功', '主机复制成功', parent=self.window())
                self.load_servers()
            except Exception as e:
                InfoBar.error('复制失败', str(e), parent=self.window())

    def edit_server(self):
        row = self.ui.server_table.currentRow()
        if row < 0: return
        server_data = self.server_data_list[row]

        dlg = ServerEditDialog(self.window(), server_data)
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("""
                        UPDATE linux_server 
                        SET servername=%s, serverip=%s, serverport=%s, serveruser=%s, serverpassword=%s, serverresult=%s 
                        WHERE serverid=%s
                    """, (data["servername"], data["serverip"], data["serverport"], data["serveruser"],
                          data["serverpassword"], data["serverresult"], server_data['serverid']))
                conn.commit()
                conn.close()
                self.load_servers()
            except Exception as e:
                InfoBar.error('更新失败', str(e), parent=self.window())

    def delete_server(self):
        row = self.ui.server_table.currentRow()
        if row < 0: return
        server_data = self.server_data_list[row]

        w = Dialog("确认删除", f"确定删除主机 {server_data['servername']} 吗？", self.window())
        if w.exec():
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("DELETE FROM linux_server WHERE serverid=%s", (server_data['serverid'],))
                conn.commit()
                conn.close()
                self.load_servers()
            except Exception as e:
                InfoBar.error('删除失败', str(e), parent=self.window())

    def open_winscp(self):
        selected_rows = self.ui.server_table.selectionModel().selectedRows()

        if len(selected_rows) > 1:
            InfoBar.warning("提示", "WinSCP 仅支持单台登录，请只选中一行服务器！", parent=self.window())
            return

        row = self.ui.server_table.currentRow()
        if row < 0:
            return

        server_data = self.server_data_list[row]

        winscp_path = None
        has_record = False
        try:
            conn = pymysql.connect(**SERVER_DB_CONFIG)
            with conn.cursor() as c:
                c.execute("SELECT exepath FROM exe_path WHERE exetype='winscp' and username= %s", (self.current_user['loginid']))
                res = c.fetchone()
                if res:
                    winscp_path = res['exepath']
                    has_record = True
            conn.close()
        except Exception as e:
            InfoBar.error('数据库错误', str(e), parent=self.window())
            return

        if not winscp_path or not os.path.exists(winscp_path):
            dlg = WinscpConfigDialog(self.window())
            if dlg.exec() and dlg.path_input.text().strip():
                winscp_path = dlg.path_input.text().strip().replace("\\", "/")

                try:
                    conn = pymysql.connect(**SERVER_DB_CONFIG)
                    with conn.cursor() as c:
                        if has_record:
                            c.execute("UPDATE exe_path SET exepath=%s WHERE exetype='winscp' and username= %s", (winscp_path,self.current_user['loginid']))
                        else:
                            c.execute("INSERT INTO exe_path (exetype, exepath, username) VALUES ('winscp', %s, %s)", (winscp_path,self.current_user['loginid']))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    InfoBar.error('保存路径失败', str(e), parent=self.window())
                    return
            else:
                return

        try:
            ip = server_data['serverip']
            port = server_data['serverport']
            user = server_data['serveruser']
            pwd = server_data['serverpassword']

            cmd = [winscp_path, f"sftp://{user}:{pwd}@{ip}:{port}/"]
            subprocess.Popen(cmd)
            InfoBar.success("启动成功", f"正在唤起 WinSCP 连接至 {server_data['servername']}", parent=self.window())
        except Exception as e:
            InfoBar.error("WinSCP 启动失败", str(e), parent=self.window())

    def filter_servers(self, text):
        search_text = text.lower()
        for i in range(self.ui.server_table.rowCount()):
            name = self.ui.server_table.item(i, 1).text().lower()
            ip = self.ui.server_table.item(i, 2).text().lower()
            match = (search_text in name) or (search_text in ip)
            self.ui.server_table.setRowHidden(i, not match)

    def open_terminal(self, item):
        row = item.row()
        server_data = self.server_data_list[row]
        key = server_data['serverid']
        tab_ip = server_data['serverip']

        if key in self.opened_sessions:
            idx = self.ui.tabs.indexOf(self.opened_sessions[key])
            if idx != -1:
                self.ui.tabs.setCurrentIndex(idx)
                return

        term_widget = SSHTerminalWidget(server_data, self)

        if self.ui.tabs.count() == 1 and self.ui.tabs.widget(0) == self.ui.welcome_page:
            self.ui.tabs.removeTab(0)

        idx = self.ui.tabs.addTab(term_widget, f"🟢 {tab_ip}")
        self.ui.tabs.setCurrentIndex(idx)
        self.opened_sessions[key] = term_widget
        term_widget.setFocus()

    def close_tab(self, index):
        widget = self.ui.tabs.widget(index)
        if widget == self.ui.welcome_page: return

        for key, w in list(self.opened_sessions.items()):
            if w == widget:
                del self.opened_sessions[key]
                break

        widget.close()
        self.ui.tabs.removeTab(index)

        if self.ui.tabs.count() == 0:
            self.ui.tabs.addTab(self.ui.welcome_page, "终端首页")