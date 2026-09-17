# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QWidget
from qfluentwidgets import (ElevatedCardWidget, TitleLabel, StrongBodyLabel,
                            IconWidget, FluentIcon, PushButton, SmoothScrollArea,
                            TransparentToolButton, BodyLabel)  # 👈 增加了 TransparentToolButton 和 BodyLabel


class Ui_Home(object):
    """ 首页的 UI 布局类 (全新任务清单版) """

    def setupUi(self, HomeInterface):
        HomeInterface.setObjectName("HomeInterface")

        self.mainLayout = QVBoxLayout(HomeInterface)
        self.mainLayout.setContentsMargins(24, 24, 24, 24)
        self.mainLayout.setSpacing(24)

        self.titleLabel = TitleLabel("工作台概览", HomeInterface)
        self.mainLayout.addWidget(self.titleLabel)

        # ================= 顶部一行：时间卡片 + 链接卡片 =================
        self.topLayout = QHBoxLayout()
        self.topLayout.setSpacing(24)
        self.mainLayout.addLayout(self.topLayout)

        # --- 卡片 1：动态时间与日期 ---
        self.timeCard = ElevatedCardWidget(HomeInterface)
        self.timeLayout = QVBoxLayout(self.timeCard)
        self.timeLayout.setAlignment(Qt.AlignCenter)

        self.lbl_time = TitleLabel("00:00:00", self.timeCard)
        self.lbl_time.setStyleSheet("font-size: 54px; font-weight: bold; font-family: 'Segoe UI', 'Microsoft YaHei';")
        self.lbl_date = StrongBodyLabel("加载中...", self.timeCard)
        self.lbl_date.setStyleSheet("color: #666666; font-size: 16px;")

        self.timeLayout.addWidget(self.lbl_time, 0, Qt.AlignHCenter)
        self.timeLayout.addSpacing(8)
        self.timeLayout.addWidget(self.lbl_date, 0, Qt.AlignHCenter)
        self.topLayout.addWidget(self.timeCard)

        # --- 卡片 2：常用系统导航 ---
        self.linkCard = ElevatedCardWidget(HomeInterface)
        self.linkLayout = QVBoxLayout(self.linkCard)
        self.linkLayout.setContentsMargins(24, 24, 24, 24)

        self.linkTitleLayout = QHBoxLayout()
        self.linkIcon = IconWidget(FluentIcon.LINK, self.linkCard)
        self.linkIcon.setFixedSize(18, 18)
        self.linkTitle = StrongBodyLabel("常用系统入口", self.linkCard)
        self.btn_config_links = PushButton("配置项", self.linkCard)
        self.btn_config_links.setFixedWidth(80)

        self.linkTitleLayout.addWidget(self.linkIcon)
        self.linkTitleLayout.addWidget(self.linkTitle)
        self.linkTitleLayout.addStretch(1)
        self.linkTitleLayout.addWidget(self.btn_config_links)
        self.linkLayout.addLayout(self.linkTitleLayout)
        self.linkLayout.addSpacing(12)

        self.linkScroll = SmoothScrollArea(self.linkCard)
        self.linkScroll.setWidgetResizable(True)
        self.linkScroll.setStyleSheet("QScrollArea{border: none; background: transparent;}")
        self.linkScroll.viewport().setStyleSheet("background-color: transparent;")

        self.linkScrollContainer = QWidget()
        self.linksContainerLayout = QVBoxLayout(self.linkScrollContainer)
        self.linksContainerLayout.setContentsMargins(0, 0, 10, 0)
        self.linksContainerLayout.setSpacing(8)
        self.linksContainerLayout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.linkScroll.setWidget(self.linkScrollContainer)
        self.linkLayout.addWidget(self.linkScroll)
        self.topLayout.addWidget(self.linkCard)

        # ================= 底部：左侧任务清单 / 右侧快捷启动 =================
        self.bottomLayout = QHBoxLayout()
        self.bottomLayout.setSpacing(24)
        self.mainLayout.addLayout(self.bottomLayout)

        # --- 👈 核心重构：底部左侧改为“任务”组件 ---
        self.taskCard = ElevatedCardWidget(HomeInterface)
        self.taskLayout = QVBoxLayout(self.taskCard)
        self.taskLayout.setContentsMargins(24, 24, 24, 24)

        # 1. 标题栏：包含图标、标题、加号、更多
        self.taskTitleLayout = QHBoxLayout()
        self.taskIcon = IconWidget(FluentIcon.COMPLETED, self.taskCard)  # 勾号图标
        self.taskIcon.setFixedSize(18, 18)
        self.taskTitle = StrongBodyLabel("任务", self.taskCard)

        self.btn_add_task = TransparentToolButton(FluentIcon.ADD, self.taskCard)
        self.btn_more_task = TransparentToolButton(FluentIcon.MORE, self.taskCard)

        self.taskTitleLayout.addWidget(self.taskIcon)
        self.taskTitleLayout.addWidget(self.taskTitle)
        self.taskTitleLayout.addStretch(1)
        self.taskTitleLayout.addWidget(self.btn_add_task)
        self.taskTitleLayout.addWidget(self.btn_more_task)

        self.taskLayout.addLayout(self.taskTitleLayout)
        self.taskLayout.addSpacing(4)

        # 2. 副标题提示
        self.taskSubtitle = BodyLabel("为会话选择任务", self.taskCard)
        self.taskSubtitle.setStyleSheet("color: #888888;")
        self.taskLayout.addWidget(self.taskSubtitle)
        self.taskLayout.addSpacing(12)

        # 3. 任务承载滚动区 (防止任务过多挤占空间)
        self.taskScroll = SmoothScrollArea(self.taskCard)
        self.taskScroll.setWidgetResizable(True)
        self.taskScroll.setStyleSheet("QScrollArea{border: none; background: transparent;}")
        self.taskScroll.viewport().setStyleSheet("background-color: transparent;")

        self.taskScrollContainer = QWidget()
        self.tasksContainerLayout = QVBoxLayout(self.taskScrollContainer)
        self.tasksContainerLayout.setContentsMargins(0, 0, 10, 0)
        self.tasksContainerLayout.setSpacing(8)
        self.tasksContainerLayout.setAlignment(Qt.AlignTop)

        self.taskScroll.setWidget(self.taskScrollContainer)
        self.taskLayout.addWidget(self.taskScroll)

        self.bottomLayout.addWidget(self.taskCard)

        # --- 底部右侧：常用软件快捷启动卡片 ---
        self.appLaunchCard = ElevatedCardWidget(HomeInterface)
        self.launchLayout = QVBoxLayout(self.appLaunchCard)
        self.launchLayout.setContentsMargins(24, 24, 24, 24)

        self.launchTitleLayout = QHBoxLayout()
        self.launchIcon = IconWidget(FluentIcon.APPLICATION, self.appLaunchCard)
        self.launchIcon.setFixedSize(18, 18)
        self.launchTitle = StrongBodyLabel("常用软件启动", self.appLaunchCard)
        self.btn_add_app = PushButton("配置项", self.appLaunchCard)
        self.btn_add_app.setFixedWidth(80)

        self.launchTitleLayout.addWidget(self.launchIcon)
        self.launchTitleLayout.addWidget(self.launchTitle)
        self.launchTitleLayout.addStretch(1)
        self.launchTitleLayout.addWidget(self.btn_add_app)
        self.launchLayout.addLayout(self.launchTitleLayout)
        self.launchLayout.addSpacing(12)

        self.appScroll = SmoothScrollArea(self.appLaunchCard)
        self.appScroll.setWidgetResizable(True)
        self.appScroll.setStyleSheet("QScrollArea{border: none; background: transparent;}")
        self.appScroll.viewport().setStyleSheet("background-color: transparent;")

        self.appScrollContainer = QWidget()
        self.appsContainerLayout = QGridLayout(self.appScrollContainer)
        self.appsContainerLayout.setContentsMargins(0, 0, 10, 0)
        self.appsContainerLayout.setSpacing(12)
        self.appsContainerLayout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.appScroll.setWidget(self.appScrollContainer)
        self.launchLayout.addWidget(self.appScroll)

        self.bottomLayout.addWidget(self.appLaunchCard)

        # 设置布局比例
        self.topLayout.setStretch(0, 1)
        self.topLayout.setStretch(1, 1)
        self.bottomLayout.setStretch(0, 1)
        self.bottomLayout.setStretch(1, 1)
        self.mainLayout.setStretch(1, 1)
        self.mainLayout.setStretch(2, 1)