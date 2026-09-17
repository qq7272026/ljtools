# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFrame, QLabel, QListWidget, QTabWidget, QWidget
from qfluentwidgets import PushButton, SearchLineEdit, ProgressBar, FluentIcon, ToolButton


class Ui_Esxi(object):
    def setupUi(self, EsxiInterface):
        EsxiInterface.setObjectName("EsxiInterface")
        self.main_lay = QHBoxLayout(EsxiInterface)
        self.main_lay.setContentsMargins(10, 10, 10, 10)
        self.main_lay.setSpacing(10)

        # ================= 1. 左侧侧边栏 (Sidebar) =================
        self.sidebar = QFrame(EsxiInterface)
        self.sidebar.setFixedWidth(280)
        self.sidebar.setStyleSheet("QFrame { background-color: transparent; }")
        self.side_lay = QVBoxLayout(self.sidebar)
        self.side_lay.setContentsMargins(0, 0, 0, 0)

        # --- 搜索与同步区域 ---
        self.search_box = QFrame(self.sidebar)
        self.search_box.setStyleSheet(
            "background: #ffffff; border-radius: 8px; padding: 10px; border: 1px solid #EBEBEB;")
        self.s_lay = QVBoxLayout(self.search_box)

        self.search_title = QLabel("🔍 全局 VM 搜索", self.search_box)
        self.search_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.s_lay.addWidget(self.search_title)

        self.sh_lay = QHBoxLayout()
        self.search_input = SearchLineEdit(self.search_box)
        self.search_input.setPlaceholderText("搜 VM 名称或 IP...")
        self.btn_search = ToolButton(FluentIcon.SEARCH, self.search_box)
        self.sh_lay.addWidget(self.search_input)
        self.sh_lay.addWidget(self.btn_search)
        self.s_lay.addLayout(self.sh_lay)

        self.btn_sync = PushButton("🚀 同步全局索引", self.search_box)
        self.s_lay.addWidget(self.btn_sync)

        self.sync_progress = ProgressBar(self.search_box)
        self.sync_progress.hide()
        self.s_lay.addWidget(self.sync_progress)

        self.side_lay.addWidget(self.search_box)

        # --- 主机列表区域 ---
        self.host_box = QFrame(self.sidebar)
        self.host_box.setStyleSheet(
            "background: #ffffff; border-radius: 8px; padding: 10px; border: 1px solid #EBEBEB;")
        self.h_lay = QVBoxLayout(self.host_box)

        self.ht_lay = QHBoxLayout()
        self.host_title = QLabel("🖥️ ESXi 服务器", self.host_box)
        self.host_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.ht_lay.addWidget(self.host_title)
        self.ht_lay.addStretch()

        self.btn_add = ToolButton(FluentIcon.ADD, self.host_box)
        self.btn_edit = ToolButton(FluentIcon.EDIT, self.host_box)
        self.btn_del = ToolButton(FluentIcon.DELETE, self.host_box)
        self.ht_lay.addWidget(self.btn_add)
        self.ht_lay.addWidget(self.btn_edit)
        self.ht_lay.addWidget(self.btn_del)
        self.h_lay.addLayout(self.ht_lay)

        self.list_widget = QListWidget(self.host_box)
        self.list_widget.setStyleSheet("""
            QListWidget { border: none; background: transparent; outline: none; }
            QListWidget::item { padding: 12px; border-bottom: 1px solid #F0F0F0; border-radius: 4px; }
            QListWidget::item:hover { background: #F3F4F6; }
            QListWidget::item:selected { background: #0078D4; color: white; font-weight: bold; }
        """)
        self.h_lay.addWidget(self.list_widget)

        self.side_lay.addWidget(self.host_box)
        self.main_lay.addWidget(self.sidebar)

        # ================= 2. 右侧 Tab 区域 =================
        self.tabs = QTabWidget(EsxiInterface)
        self.tabs.setTabsClosable(True)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #EBEBEB; border-radius: 8px; background: white; }
            QTabBar::tab { background: #F3F4F6; color: #333; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
            QTabBar::tab:selected { background: white; color: #0078D4; font-weight: bold; border-bottom: 2px solid #0078D4; }
            QTabBar::close-button { image: url(:/qfluentwidgets/images/icons/Close_black.svg); subcontrol-position: right; }
        """)
        self.welcome = QLabel("👋 请在左侧选择服务器以开始管理\n\n支持多标签页操作\n每个标签页独立保持登录状态",
                              alignment=Qt.AlignCenter)
        self.welcome.setStyleSheet("font-size: 16px; color: #888;")
        self.tabs.addTab(self.welcome, "首页")

        self.main_lay.addWidget(self.tabs)