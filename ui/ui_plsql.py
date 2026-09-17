# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QHeaderView, QAbstractItemView
from qfluentwidgets import (PushButton, LineEdit, RadioButton,
                            TableWidget, FluentIcon, StrongBodyLabel, SearchLineEdit)


class Ui_Plsql(object):
    def setupUi(self, PlsqlInterface):
        PlsqlInterface.setObjectName("PlsqlInterface")
        self.mainLayout = QVBoxLayout(PlsqlInterface)
        self.mainLayout.setContentsMargins(24, 24, 24, 24)
        self.mainLayout.setSpacing(16)

        # ================= 1. 第一排：核心操作按钮 =================
        self.topToolbarLayout = QHBoxLayout()
        self.topToolbarLayout.setSpacing(8)

        self.btn_refresh = PushButton("刷新", PlsqlInterface)
        self.btn_refresh.setIcon(FluentIcon.UPDATE)

        self.btn_copy = PushButton("复制", PlsqlInterface)
        self.btn_copy.setIcon(FluentIcon.COPY)

        self.btn_add = PushButton("新增", PlsqlInterface)
        self.btn_add.setIcon(FluentIcon.ADD)

        self.btn_edit = PushButton("修改", PlsqlInterface)
        self.btn_edit.setIcon(FluentIcon.EDIT)

        self.btn_delete = PushButton("删除", PlsqlInterface)
        self.btn_delete.setIcon(FluentIcon.DELETE)

        self.btn_save = PushButton("保存", PlsqlInterface)
        self.btn_save.setIcon(FluentIcon.SAVE)

        self.btn_select_all = PushButton("全选", PlsqlInterface)
        self.btn_select_all.setIcon(FluentIcon.ACCEPT)

        self.btn_login = PushButton("登录", PlsqlInterface)
        self.btn_login.setIcon(FluentIcon.PEOPLE)

        self.btn_batch_edit = PushButton("批量修改", PlsqlInterface)
        self.btn_batch_edit.setIcon(FluentIcon.UPDATE)

        self.btn_test = PushButton("测试", PlsqlInterface)
        self.btn_test.setIcon(FluentIcon.SYNC)

        for btn in [self.btn_refresh, self.btn_copy, self.btn_add, self.btn_edit,
                    self.btn_delete, self.btn_save, self.btn_select_all, self.btn_login, self.btn_batch_edit,self.btn_test]:
            self.topToolbarLayout.addWidget(btn)
        self.topToolbarLayout.addStretch(1)

        # ================= 2. 第二排：查询、单选、程序路径 =================
        self.filterLayout = QHBoxLayout()
        self.filterLayout.setSpacing(12)

        # self.btn_query = PushButton("查询", PlsqlInterface)
        # self.btn_query.setIcon(FluentIcon.SEARCH)

        self.search_input = SearchLineEdit(PlsqlInterface)
        self.search_input.setPlaceholderText("输入关键字...")
        self.search_input.setFixedWidth(200)

        self.path_label = StrongBodyLabel("程序路径:", PlsqlInterface)
        self.path_input = LineEdit(PlsqlInterface)
        self.path_input.setPlaceholderText("请选择或输入路径...")
        self.path_input.setMinimumWidth(250)
        self.btn_browse = PushButton("选择文件", PlsqlInterface)

        #self.filterLayout.addWidget(self.btn_query)
        self.filterLayout.addWidget(self.search_input)

        self.filterLayout.addSpacing(24)
        self.filterLayout.addWidget(self.path_label)
        self.filterLayout.addWidget(self.path_input)
        self.filterLayout.addWidget(self.btn_browse)
        self.filterLayout.addStretch(1)

        # ================= 3. 主体：数据表格 =================
        self.tableWidget = TableWidget(PlsqlInterface)
        self.tableWidget.setWordWrap(False)

        headers = ['数据库id', '数据库IP', '数据库名称', '数据库用户名', '数据库密码', '数据库端口',
                   '数据库实例名', '数据库测试结果', '状态']
        self.tableWidget.setColumnCount(len(headers))
        self.tableWidget.setHorizontalHeaderLabels(headers)

        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableWidget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tableWidget.setSortingEnabled(False)
        # 👈 核心修改：打造极简无边框样式
        self.tableWidget.setShowGrid(False)  # 关闭原生网格
        self.tableWidget.setBorderVisible(False)  # 隐藏外边框
        #利用 QSS 仅保留极淡的横向分割线，以及微软蓝选中高亮
        self.tableWidget.setStyleSheet("""
            QTableView::item:selected {
                background-color: #7EC0EE;
            }
        """)

        self.tableWidget.setColumnWidth(0, 100)
        self.tableWidget.setColumnWidth(1, 160)
        self.tableWidget.setColumnWidth(2, 180)
        self.tableWidget.setColumnWidth(4, 150)
        self.tableWidget.setColumnWidth(8, 100)

        self.mainLayout.addLayout(self.topToolbarLayout)
        self.mainLayout.addLayout(self.filterLayout)
        self.mainLayout.addWidget(self.tableWidget)