# coding:utf-8
from PyQt5.QtCore import pyqtSignal
from qfluentwidgets import MessageBox, RoundMenu, Action

# 导入 UI 界面
from main_ui import Ui_Window


class Window(Ui_Window):
    """ 主界面逻辑层 """
    logout_signal = pyqtSignal()

    def __init__(self, user_info=None):
        super().__init__()
        # 这里的 self.incaInterface 是在 Ui_Window 中实例化的
        # 我们需要在 __init__ 执行完后，把 user_info 注入给它
        # 【关键】把传入的参数存进实例属性
        self.user_info = user_info
        # 3. 注入给接口
        if self.incaInterface:
            self.incaInterface.current_user = self.user_info
        if self.plsqlInterface:
            self.plsqlInterface.current_user = self.user_info
        if self.linuxInterface:
            self.linuxInterface.current_user = self.user_info
        self.stackWidget.currentChanged.connect(self.onCurrentInterfaceChanged)

    def switchTo(self, widget):
        self.stackWidget.setCurrentWidget(widget)

    def onCurrentInterfaceChanged(self, index):
        widget = self.stackWidget.widget(index)
        self.navigationBar.setCurrentItem(widget.objectName())

    def showMessageBox(self):
        w = MessageBox('帮助文档', '这是以后给你的管理工具写说明书的地方。', self)
        w.yesButton.setText('我知道了')
        w.cancelButton.setText('取消')
        if w.exec(): pass

    def set_user_menu(self, user_name):
        """ 接收用户名，并生成下拉菜单 """
        menu = RoundMenu(parent=self)

        name_action = Action(f"当前用户: {user_name}", self)
        name_action.setEnabled(False)
        menu.addAction(name_action)

        menu.addSeparator()

        exit_action = Action("退出登录", self)
        exit_action.triggered.connect(self.logout)
        menu.addAction(exit_action)

        self.titleBar.avatar.setMenu(menu)

    def logout(self):
        """ 发射退出信号 """
        self.logout_signal.emit()

# ⚠️ 注意：这里没有 if __name__ == '__main__': 了