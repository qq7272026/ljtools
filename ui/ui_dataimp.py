# ui/ui_dataimp.py
# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QFrame, QLabel, QSplitter, QAbstractItemView, QHeaderView
from qfluentwidgets import ToolButton, PushButton, PrimaryPushButton, ComboBox, FluentIcon, SearchLineEdit, TableWidget, \
    PlainTextEdit, LineEdit


class Ui_DataImp(object):
    def setupUi(self, DataImpInterface):
        DataImpInterface.setObjectName("DataImpInterface")
        self.main_lay = QHBoxLayout(DataImpInterface)
        self.main_lay.setContentsMargins(10, 10, 10, 10)
        self.main_lay.setSpacing(10)

        # ================= 1. 左侧：数据库会话管理器 =================
        self.sidebar = QFrame(DataImpInterface)
        # 👈 扩大左侧栏宽度到 380，给四列腾出充足空间
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
        # 👈 修改为 4 列，并加入了用户名
        self.db_table.setColumnCount(4)
        self.db_table.setHorizontalHeaderLabels(['状态', '名称', 'IP地址', '用户名'])
        self.db_table.verticalHeader().hide()

        # 👈 设置各列的交互模式，允许拖拽
        self.db_table.setColumnWidth(0, 28)
        self.db_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)  # 状态极窄且固定
        self.db_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)  # 名称可拖拽
        self.db_table.setColumnWidth(1, 110)
        self.db_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)  # IP 可拖拽
        self.db_table.setColumnWidth(2, 110)
        self.db_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # 用户名填满剩余空间

        self.db_table.setShowGrid(False)
        self.db_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.db_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.db_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.db_table.setAlternatingRowColors(True)

        # 👈 核心修复：注入浅蓝色选中背景样式
        self.db_table.setStyleSheet("""
            QTableView::item:selected {
                background-color: #D9EBF9;
                color: #000000;
            }
        """)

        self.side_lay.addWidget(self.db_table)
        self.main_lay.addWidget(self.sidebar)

        # ================= 2. 右侧：导入操作区 =================
        self.right_panel = QFrame(DataImpInterface)
        self.right_panel.setStyleSheet("background: #ffffff; border-radius: 8px; border: 1px solid #EBEBEB;")
        self.right_lay = QVBoxLayout(self.right_panel)
        self.right_lay.setContentsMargins(15, 15, 15, 15)
        self.right_lay.setSpacing(10)

        # --- 2.1 顶部操作工具栏 ---
        self.toolbar_lay1 = QHBoxLayout()
        self.btn_select_table = PushButton("选择目标表名", self.right_panel)
        self.btn_select_table.setIcon(FluentIcon.MENU)
        self.line_table_name = LineEdit(self.right_panel)
        self.line_table_name.setPlaceholderText("请先在左侧选择数据库，然后点击左侧按钮加载表名...")
        self.line_table_name.setReadOnly(True)

        self.toolbar_lay1.addWidget(self.btn_select_table)
        self.toolbar_lay1.addWidget(self.line_table_name, 1)
        self.right_lay.addLayout(self.toolbar_lay1)

        self.toolbar_lay2 = QHBoxLayout()
        self.btn_select_file = PushButton("选择数据文件", self.right_panel)
        self.btn_select_file.setIcon(FluentIcon.FOLDER)

        self.combo_file_type = ComboBox(self.right_panel)
        self.combo_file_type.addItems(["CSV (逗号分隔)", "TXT (制表符分隔)", "TXT (管道符 | 分隔)"])
        self.combo_file_type.setFixedWidth(160)

        self.btn_gen_config = PushButton("生成配置文件", self.right_panel)
        self.btn_gen_config.setIcon(FluentIcon.DOCUMENT)
        # 👈 新增：清空按钮
        self.btn_clear = PushButton("清空", self.right_panel)
        self.btn_clear.setIcon(FluentIcon.DELETE)

        self.btn_import = PrimaryPushButton("开始导入 (SQL*Loader)", self.right_panel)
        self.btn_import.setIcon(FluentIcon.PLAY)

        self.toolbar_lay2.addWidget(self.btn_select_file)
        self.toolbar_lay2.addWidget(self.combo_file_type)
        self.toolbar_lay2.addWidget(self.btn_gen_config)
        self.toolbar_lay2.addWidget(self.btn_clear)  # 👈 加到生成配置右侧
        self.toolbar_lay2.addStretch()
        self.toolbar_lay2.addWidget(self.btn_import)

        self.right_lay.addLayout(self.toolbar_lay2)

        # --- 2.2 数据展示与配置代码区 ---
        self.splitter = QSplitter(Qt.Vertical, self.right_panel)

        self.preview_table = TableWidget(self.splitter)
        self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_table.setShowGrid(True)

        self.mapping_table = TableWidget(self.splitter)
        self.mapping_table.setColumnCount(4)
        self.mapping_table.setHorizontalHeaderLabels(
            ['CSV 文件表头', 'Oracle 目标列名', '字段数据类型', '日期格式化代码'])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mapping_table.setShowGrid(True)
        self.mapping_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.ctl_text = PlainTextEdit(self.splitter)
        self.ctl_text.setPlaceholderText("生成的 sqlldr 控制文件 (.ctl) 内容将显示在这里，支持手动修改...")
        self.ctl_text.setStyleSheet("""
            QPlainTextEdit {
                font-family: 'Consolas', monospace;
                font-size: 13px;
                background-color: #F8F9FA;
                border: 1px solid #EAEAEA;
                border-radius: 4px;
                padding: 10px;
            }
        """)

        self.splitter.setSizes([200, 350, 250])
        self.right_lay.addWidget(self.splitter)

        self.main_lay.addWidget(self.right_panel)