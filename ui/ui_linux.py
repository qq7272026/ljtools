# ui/ui_linux.py
# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFrame, QLabel, QTabWidget, QHeaderView, QAbstractItemView
from qfluentwidgets import ToolButton, FluentIcon, SearchLineEdit, TableWidget


class Ui_Linux(object):
    def setupUi(self, LinuxInterface):
        LinuxInterface.setObjectName("LinuxInterface")
        self.main_lay = QHBoxLayout(LinuxInterface)
        self.main_lay.setContentsMargins(10, 10, 10, 10)
        self.main_lay.setSpacing(10)

        # ================= 1. 左侧：服务器会话管理器 =================
        self.sidebar = QFrame(LinuxInterface)
        self.sidebar.setFixedWidth(300)
        self.sidebar.setStyleSheet("background: #ffffff; border-radius: 8px; border: 1px solid #EBEBEB;")
        self.side_lay = QVBoxLayout(self.sidebar)
        self.side_lay.setContentsMargins(10, 10, 10, 10)

        self.header_lay = QHBoxLayout()
        self.title_lbl = QLabel("🐧主机", self.sidebar)
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 15px;")
        self.header_lay.addWidget(self.title_lbl)
        self.header_lay.addStretch()

        self.btn_test = ToolButton(FluentIcon.WIFI, self.sidebar)
        self.btn_test.setToolTip("测试选中的主机 (支持 Ctrl/Shift 多选)")

        self.btn_add = ToolButton(FluentIcon.ADD, self.sidebar)
        self.btn_add.setToolTip("新建主机")

        # 👈 新增复制按钮
        self.btn_copy = ToolButton(FluentIcon.COPY, self.sidebar)
        self.btn_copy.setToolTip("复制选中主机")

        self.btn_edit = ToolButton(FluentIcon.EDIT, self.sidebar)
        self.btn_edit.setToolTip("修改选中主机")

        self.btn_del = ToolButton(FluentIcon.DELETE, self.sidebar)
        self.btn_del.setToolTip("删除选中主机")

        self.header_lay.addWidget(self.btn_test)
        self.header_lay.addWidget(self.btn_add)
        self.header_lay.addWidget(self.btn_copy)  # 添加到布局中
        self.header_lay.addWidget(self.btn_edit)
        self.header_lay.addWidget(self.btn_del)
        self.side_lay.addLayout(self.header_lay)

        self.search_input = SearchLineEdit(self.sidebar)
        self.search_input.setPlaceholderText("搜索服务器名称或 IP...")
        self.side_lay.addWidget(self.search_input)

        # ================= 表格 UI 极致优化 =================
        self.server_table = TableWidget(self.sidebar)
        self.server_table.setColumnCount(3)
        self.server_table.setHorizontalHeaderLabels(['状态', '名称', 'IP地址'])
        self.server_table.verticalHeader().hide()

        self.server_table.setColumnWidth(0, 28)
        self.server_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)

        self.server_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.server_table.setColumnWidth(1, 130)

        self.server_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

        self.server_table.setShowGrid(False)
        self.server_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.server_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.server_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.server_table.setAlternatingRowColors(True)
        # 👈 核心修复：注入浅蓝色选中背景样式
        self.server_table.setStyleSheet("""
            QTableView::item:selected {
                background-color: #D9EBF9;
                color: #000000;
            }
        """)

        self.side_lay.addWidget(self.server_table)

        self.main_lay.addWidget(self.sidebar)

        # ================= 2. 右侧：多标签 SSH 终端区域 =================
        self.tabs = QTabWidget(LinuxInterface)
        self.tabs.setTabsClosable(True)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #EBEBEB; border-radius: 8px; background: #1E1E1E; }
            QTabBar::tab { background: #F3F4F6; color: #333; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
            QTabBar::tab:selected { background: #1E1E1E; color: #4AF626; font-weight: bold; border-bottom: 2px solid #4AF626; }
            QTabBar::close-button { image: url(:/qfluentwidgets/images/icons/Close_black.svg); subcontrol-position: right; }
        """)

        self.welcome_page = QFrame()
        self.welcome_page.setStyleSheet("background: #1E1E1E; border-radius: 8px;")
        welcome_lay = QVBoxLayout(self.welcome_page)
        self.welcome_lbl = QLabel("Terminal Ready.\n\n请在左侧双击服务器建立 SSH 连接...", self.welcome_page)
        self.welcome_lbl.setAlignment(Qt.AlignCenter)
        self.welcome_lbl.setStyleSheet("color: #888888; font-size: 16px; font-family: Consolas, monospace;")
        welcome_lay.addWidget(self.welcome_lbl)

        self.tabs.addTab(self.welcome_page, "终端首页")
        self.main_lay.addWidget(self.tabs)