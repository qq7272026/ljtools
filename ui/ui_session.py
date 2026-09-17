# ui/ui_session.py
# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFrame, QLabel, QSplitter, QAbstractItemView, QHeaderView, \
    QTabWidget, QWidget
from qfluentwidgets import ToolButton, PushButton, PrimaryPushButton, ComboBox, FluentIcon, SearchLineEdit, TableWidget, \
    PlainTextEdit, CheckBox


class Ui_Session(object):
    def setupUi(self, SessionInterface):
        SessionInterface.setObjectName("SessionInterface")
        self.main_lay = QHBoxLayout(SessionInterface)
        self.main_lay.setContentsMargins(10, 10, 10, 10)
        self.main_lay.setSpacing(10)

        # ================= 1. 左侧：数据库会话管理器 =================
        self.sidebar = QFrame(SessionInterface)
        self.sidebar.setFixedWidth(380)
        self.sidebar.setStyleSheet("background: #ffffff; border-radius: 8px; border: 1px solid #EBEBEB;")
        self.side_lay = QVBoxLayout(self.sidebar)
        self.side_lay.setContentsMargins(10, 10, 10, 10)

        self.header_lay = QHBoxLayout()
        self.title_lbl = QLabel("🛢️ 目标数据库", self.sidebar)
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 15px;")
        self.header_lay.addWidget(self.title_lbl)
        self.header_lay.addStretch()

        self.btn_test = ToolButton(FluentIcon.WIFI, self.sidebar)
        self.btn_test.setToolTip("测试选中的数据库 (支持多选)")
        self.btn_add = ToolButton(FluentIcon.ADD, self.sidebar)
        self.btn_copy = ToolButton(FluentIcon.COPY, self.sidebar)
        self.btn_edit = ToolButton(FluentIcon.EDIT, self.sidebar)
        self.btn_del = ToolButton(FluentIcon.DELETE, self.sidebar)

        self.header_lay.addWidget(self.btn_test)
        self.header_lay.addWidget(self.btn_add)
        self.header_lay.addWidget(self.btn_copy)
        self.header_lay.addWidget(self.btn_edit)
        self.header_lay.addWidget(self.btn_del)
        self.side_lay.addLayout(self.header_lay)

        self.search_input = SearchLineEdit(self.sidebar)
        self.search_input.setPlaceholderText("搜索名称、IP 或用户名...")
        self.side_lay.addWidget(self.search_input)

        self.db_table = TableWidget(self.sidebar)
        self.db_table.setColumnCount(4)
        self.db_table.setHorizontalHeaderLabels(['状态', '名称', 'IP地址', '用户名'])
        self.db_table.verticalHeader().hide()

        self.db_table.setColumnWidth(0, 28)
        self.db_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.db_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.db_table.setColumnWidth(1, 110)
        self.db_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.db_table.setColumnWidth(2, 110)
        self.db_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        self.db_table.setShowGrid(False)
        self.db_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.db_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.db_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.db_table.setAlternatingRowColors(True)

        self.db_table.setStyleSheet("""
            QTableView::item:selected {
                background-color: #D9EBF9;
                color: #000000;
            }
        """)
        self.side_lay.addWidget(self.db_table)
        self.main_lay.addWidget(self.sidebar)

        # ================= 2. 右侧：会话监控与操作区 =================
        self.right_panel = QFrame(SessionInterface)
        self.right_panel.setStyleSheet("background: #ffffff; border-radius: 8px; border: 1px solid #EBEBEB;")
        self.right_lay = QVBoxLayout(self.right_panel)
        self.right_lay.setContentsMargins(15, 15, 15, 15)
        self.right_lay.setSpacing(10)

        # --- 2.1 顶部工具栏 ---
        self.toolbar_lay = QHBoxLayout()

        self.btn_refresh = PushButton("加载会话", self.right_panel)
        self.btn_refresh.setIcon(FluentIcon.SYNC)

        self.combo_status = ComboBox(self.right_panel)
        self.combo_status.addItems(["ACTIVE", "INACTIVE", "ALL", "KILLED"])
        self.combo_status.setFixedWidth(120)

        self.chk_bind = CheckBox("显示绑定变量值", self.right_panel)

        # 👈 UI 修复 5：使用原生风格的次级主按钮，去掉难看的硬编码红色
        self.btn_kill = PushButton("强制结束会话", self.right_panel)
        self.btn_kill.setIcon(FluentIcon.DELETE)

        self.toolbar_lay.addWidget(self.btn_refresh)
        self.toolbar_lay.addWidget(QLabel("状态过滤:", self.right_panel))
        self.toolbar_lay.addWidget(self.combo_status)
        self.toolbar_lay.addWidget(self.chk_bind)
        self.toolbar_lay.addStretch()
        self.toolbar_lay.addWidget(self.btn_kill)

        self.right_lay.addLayout(self.toolbar_lay)

        # --- 2.2 上下拖拽分割器 ---
        self.splitter = QSplitter(Qt.Vertical, self.right_panel)

        # [上部]：会话列表
        self.session_table = TableWidget(self.splitter)
        # 👉 UI 动态优化：区分 SQL 执行时间与会话登录时间
        self.session_table.setColumnCount(12)
        self.session_table.setHorizontalHeaderLabels(['行号', 'SQL_ID', 'SQL 开始执行时间', '当前时间', '主机名', '会话ID (SID)','序列号', '用户名称', '状态', '客户端名称', 'SQL语句 (截断)', 'CACHE_KEY'
        ])

        self.session_table.setColumnWidth(0, 50)  # 行号
        self.session_table.setColumnWidth(1, 120)  # SQL_ID
        self.session_table.setColumnWidth(2, 150)  # SQL 开始执行时间
        self.session_table.setColumnWidth(3, 150)  # 会话登录时间
        self.session_table.setColumnWidth(4, 100)  # 主机名
        self.session_table.setColumnWidth(5, 90)  # SID
        self.session_table.setColumnWidth(6, 80)  # 序列号
        self.session_table.setColumnWidth(7, 100)  # 用户名
        self.session_table.setColumnWidth(8, 80)  # 状态
        self.session_table.setColumnWidth(9, 100)  # 客户端名称

        # 让 SQL语句(截断) 列自动拉伸填满剩余空间
        self.session_table.horizontalHeader().setSectionResizeMode(10, QHeaderView.Stretch)
        # 隐藏最后一个缓存辅助列 (索引由10变成了11)
        self.session_table.setColumnHidden(11, True)
        # 
        # self.session_table.setColumnCount(11)
        # self.session_table.setHorizontalHeaderLabels([
        #     '行号', '开始执行时间', '当前时间', '主机名', '会话ID (SID)',
        #     '序列号', '用户名称', '状态', '客户端名称', 'SQL语句 (截断)', 'SQL_ID_CHILD'
        # ])
        # self.session_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # self.session_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Stretch)
        # self.session_table.setColumnHidden(10, True)
        self.session_table.setShowGrid(True)
        self.session_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.session_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.session_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.session_table.setStyleSheet("QTableView::item:selected { background-color: #D9EBF9; color: #000000; }")

        # [下部]：多功能标签页
        self.tab_widget = QTabWidget(self.splitter)
        self.tab_widget.setStyleSheet("""
            QTabBar::tab { padding: 8px 20px; font-weight: bold; }
            QTabBar::tab:selected { color: #0066cc; border-bottom: 2px solid #0066cc; }
        """)

        # --- 标签 1: 完整 SQL 语句 ---
        self.tab_sql = QWidget()
        self.tab_sql_lay = QVBoxLayout(self.tab_sql)
        self.sql_text = PlainTextEdit(self.tab_sql)
        self.sql_text.setReadOnly(True)
        self.sql_text.setStyleSheet("font-family: 'Consolas'; font-size: 13px; background: #F8F9FA;")
        self.tab_sql_lay.addWidget(self.sql_text)
        self.tab_widget.addTab(self.tab_sql, "💻 SQL 语句")

        # --- 标签 2: 执行计划 ---
        self.tab_plan = QWidget()
        self.tab_plan_lay = QVBoxLayout(self.tab_plan)

        self.plan_toolbar = QHBoxLayout()
        self.combo_plan_format = ComboBox(self.tab_plan)
        self.combo_plan_format.addItems(["TYPICAL", "BASIC", "ALL", "ADVANCED"])
        self.btn_ai_analysis = PushButton("✨ AI 分析", self.tab_plan)

        self.plan_toolbar.addWidget(QLabel("显示模式:"))
        self.plan_toolbar.addWidget(self.combo_plan_format)
        self.plan_toolbar.addStretch()
        self.plan_toolbar.addWidget(self.btn_ai_analysis)

        self.plan_text = PlainTextEdit(self.tab_plan)
        self.plan_text.setReadOnly(True)
        self.plan_text.setStyleSheet("font-family: 'Consolas'; font-size: 13px; background: #1E1E1E; color: #4AF626;")
        self.tab_plan_lay.addLayout(self.plan_toolbar)
        self.tab_plan_lay.addWidget(self.plan_text)
        self.tab_widget.addTab(self.tab_plan, "📈 执行计划")

        # --- 标签 3: 杀会话语句记录 (修改列以适配预览) ---
        self.tab_kill = QWidget()
        self.tab_kill_lay = QVBoxLayout(self.tab_kill)
        self.kill_table = TableWidget(self.tab_kill)
        self.kill_table.setColumnCount(3)
        self.kill_table.setHorizontalHeaderLabels(['行号', '待执行/已执行的命令', '状态'])
        self.kill_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.kill_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.kill_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tab_kill_lay.addWidget(self.kill_table)
        self.tab_widget.addTab(self.tab_kill, "⚔️ 杀会话操作")

        # --- 标签 4: 关联对象信息 (改为解析 SQL 涉及对象) ---
        self.tab_obj = QWidget()
        self.tab_obj_lay = QVBoxLayout(self.tab_obj)
        self.obj_table = TableWidget(self.tab_obj)
        self.obj_table.setColumnCount(4)
        self.obj_table.setHorizontalHeaderLabels(['SQL_ID', '对象所有者', '对象名称', '对象类型'])
        self.obj_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.obj_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.obj_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tab_obj_lay.addWidget(self.obj_table)
        self.tab_widget.addTab(self.tab_obj, "📦 语句涉及对象")

        self.splitter.setSizes([400, 300])
        self.right_lay.addWidget(self.splitter)
        self.main_lay.addWidget(self.right_panel)