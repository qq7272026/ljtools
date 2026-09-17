# coding:utf-8
import os
import json  # 👈 新增：用于存取本地配置文件
from PyQt5.QtCore import Qt, pyqtSignal, QEasingCurve, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QApplication, QFrame, QWidget

from qfluentwidgets import (NavigationBar, NavigationItemPosition,
                            isDarkTheme, SearchLineEdit, PopUpAniStackedWidget,
                            TransparentDropDownToolButton, CheckBox)  # 👈 新增 CheckBox 导入
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, TitleBar

from pages.home_interface import HomeInterface
from pages.inca_interface import IncaInterface
from pages.plsql_interface import PlsqlInterface
from pages.esxi_interface import EsxiInterface
from pages.linux_interface import LinuxInterface
from pages.dataimp_interface import DataImpInterface
from pages.session_interface import SessionInterface
# 定义全局配置文件名
WINDOW_CONFIG_FILE = "window_config.json"


class Widget(QWidget):
    """ 用于临时占位的假页面 """

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel(text, self)
        self.label.setAlignment(Qt.AlignCenter)
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)
        self.setObjectName(text.replace(' ', '-'))


class StackedWidget(QFrame):
    """ Stacked widget 页面堆叠管理器 """
    currentChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.view = PopUpAniStackedWidget(self)

        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.addWidget(self.view)
        self.view.currentChanged.connect(self.currentChanged)

    def addWidget(self, widget):
        self.view.addWidget(widget)

    def widget(self, index: int):
        return self.view.widget(index)

    def setCurrentWidget(self, widget, popOut=False):
        if not popOut:
            self.view.setCurrentWidget(widget, duration=300)
        else:
            self.view.setCurrentWidget(widget, True, False, 200, QEasingCurve.InQuad)

    def setCurrentIndex(self, index, popOut=False):
        self.setCurrentWidget(self.view.widget(index), popOut)


class CustomTitleBar(TitleBar):
    """ 自定义标题栏 (包含搜索、最大化复选框、头像) """

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.hBoxLayout.removeWidget(self.minBtn)
        self.hBoxLayout.removeWidget(self.maxBtn)
        self.hBoxLayout.removeWidget(self.closeBtn)

        # 1. add window icon
        self.iconLabel = QLabel(self)
        self.iconLabel.setFixedSize(18, 18)
        self.hBoxLayout.insertSpacing(0, 20)
        self.hBoxLayout.insertWidget(1, self.iconLabel, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.window().windowIconChanged.connect(self.setIcon)

        # 2. add title label
        self.titleLabel = QLabel(self)
        self.hBoxLayout.insertWidget(2, self.titleLabel, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.titleLabel.setObjectName('titleLabel')
        self.window().windowTitleChanged.connect(self.setTitle)

        # 3. add search line edit
        self.searchLineEdit = SearchLineEdit(self)
        self.searchLineEdit.setPlaceholderText('搜索应用等')
        self.searchLineEdit.setFixedWidth(400)
        self.searchLineEdit.setClearButtonEnabled(True)

        # 4. 👈 新增：添加“启动时最大化”复选框
        self.maximizeCheckBox = CheckBox('最大化', self)
        self.maximizeCheckBox.stateChanged.connect(self.save_window_config)  # 绑定保存事件
        self.hBoxLayout.insertWidget(7, self.maximizeCheckBox, 0, Qt.AlignRight)
        self.hBoxLayout.insertSpacing(8, 16)  # 增加一些间距

        # 5. add avatar
        self.avatar = TransparentDropDownToolButton('resource/imgs/shoko.png', self)
        self.avatar.setIconSize(QSize(26, 26))
        self.avatar.setFixedHeight(30)
        self.hBoxLayout.insertWidget(9, self.avatar, 0, Qt.AlignRight)
        self.hBoxLayout.insertSpacing(10, 20)

        # 6. 右侧窗口控制按钮 (最小化、最大化、关闭)
        self.vBoxLayout = QVBoxLayout()
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setSpacing(0)
        self.buttonLayout.setContentsMargins(0, 0, 0, 0)
        self.buttonLayout.setAlignment(Qt.AlignTop)
        self.buttonLayout.addWidget(self.minBtn)
        self.buttonLayout.addWidget(self.maxBtn)
        self.buttonLayout.addWidget(self.closeBtn)
        self.vBoxLayout.addLayout(self.buttonLayout)
        self.vBoxLayout.addStretch(1)
        self.hBoxLayout.addLayout(self.vBoxLayout, 0)

    def save_window_config(self):
        """ 👈 新增：将最大化配置持久化到本地 JSON """
        config = {"auto_maximize": self.maximizeCheckBox.isChecked()}
        try:
            with open(WINDOW_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存主窗口配置失败: {e}")

    def setTitle(self, title):
        self.titleLabel.setText(title)
        self.titleLabel.adjustSize()

    def setIcon(self, icon):
        self.iconLabel.setPixmap(QIcon(icon).pixmap(18, 18))

    def resizeEvent(self, e):
        # 居中显示搜索框
        self.searchLineEdit.move((self.width() - self.searchLineEdit.width()) // 2, 8)


class Ui_Window(FramelessWindow):
    """ 纯 UI 布局层，不包含复杂的业务逻辑 """

    def __init__(self):
        super().__init__()
        self.setTitleBar(CustomTitleBar(self))

        self.hBoxLayout = QHBoxLayout(self)
        self.navigationBar = NavigationBar(self)
        self.stackWidget = StackedWidget(self)

        # create sub interface
        self.homeInterface = HomeInterface(self)
        self.incaInterface = IncaInterface(self)
        self.incaInterface.setObjectName('Inca Interface')
        self.plsqlInterface = PlsqlInterface(self)
        self.plsqlInterface.setObjectName('Plsql Interface')
        self.esxiInterface = EsxiInterface(self)
        self.esxiInterface.setObjectName('Esxi Interface')
        self.linuxInterface = LinuxInterface(self)
        self.linuxInterface.setObjectName('Linux Interface')
        self.dataImpInterface = DataImpInterface(self)
        self.dataImpInterface.setObjectName('DataImp Interface')
        self.sessionInterface = SessionInterface(self)
        self.sessionInterface.setObjectName('Session Interface')


        self.libraryInterface = Widget('library Interface', self)

        self.initLayout()
        self.initNavigation()
        self.initWindow()

    def initLayout(self):
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, 48, 0, 0)
        self.hBoxLayout.addWidget(self.navigationBar)
        self.hBoxLayout.addWidget(self.stackWidget)
        self.hBoxLayout.setStretchFactor(self.stackWidget, 1)

    def initNavigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, '主页', selectedIcon=FIF.HOME_FILL)
        self.addSubInterface(self.incaInterface, "resource/imgs/inca.ico", '英克')
        self.addSubInterface(self.plsqlInterface, "resource/imgs/plsql.ico", 'plsql')
        self.addSubInterface(self.esxiInterface, FIF.MENU, 'esxi')
        self.addSubInterface(self.linuxInterface,FIF.ZOOM,'linux')
        self.addSubInterface(self.dataImpInterface, FIF.IMAGE_EXPORT, '数据导入')
        self.addSubInterface(self.sessionInterface, FIF.MESSAGE, '会话管理')
        self.addSubInterface(self.libraryInterface, FIF.BOOK_SHELF, '库', NavigationItemPosition.BOTTOM,
                             FIF.LIBRARY_FILL)

        self.navigationBar.addItem(
            routeKey='Help',
            icon=FIF.HELP,
            text='帮助',
            onClick=self.showMessageBox,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )
        self.navigationBar.setCurrentItem(self.homeInterface.objectName())

    def initWindow(self):
        # 1. 👈 设定默认大小为 1300 x 900
        self.resize(1300, 900)

        self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('立健工具箱')
        self.titleBar.setAttribute(Qt.WA_StyledBackground)

        # 2. 居中显示算法
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        self.setQss()

        # 3. 👈 新增：读取本地配置，判断是否需要启动全屏
        is_maximized = False
        if os.path.exists(WINDOW_CONFIG_FILE):
            try:
                with open(WINDOW_CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    is_maximized = config.get("auto_maximize", False)
            except Exception:
                pass

        # 临时屏蔽信号，防止在初始化打勾时触发“保存”动作
        self.titleBar.maximizeCheckBox.blockSignals(True)
        self.titleBar.maximizeCheckBox.setChecked(is_maximized)
        self.titleBar.maximizeCheckBox.blockSignals(False)

        # 如果用户上次勾选了最大化，则直接触发全屏
        if is_maximized:
            self.showMaximized()

    def addSubInterface(self, interface, icon, text: str, position=NavigationItemPosition.TOP, selectedIcon=None):
        self.stackWidget.addWidget(interface)
        self.navigationBar.addItem(
            routeKey=interface.objectName(),
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface),
            selectedIcon=selectedIcon,
            position=position,
        )

    def setQss(self):
        color = 'dark' if isDarkTheme() else 'light'
        qss_path = f'resource/{color}/demo.qss'
        if os.path.exists(qss_path):
            with open(qss_path, encoding='utf-8') as f:
                self.setStyleSheet(f.read())

    # --- 下面是预留给逻辑层的接口方法 ---
    def switchTo(self, widget):
        pass

    def showMessageBox(self):
        pass