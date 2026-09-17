# coding:utf-8
import os
import json
import subprocess
from PyQt5.QtCore import QTimer, QDateTime, Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFileDialog,
                             QApplication, QSizePolicy, QGraphicsColorizeEffect)
from PyQt5.QtGui import QFontMetrics, QFont, QColor
from qfluentwidgets import (MessageBoxBase, SubtitleLabel, LineEdit, FluentIcon,
                            SmoothScrollArea, ToolButton, PushButton, CardWidget,
                            BodyLabel, IconWidget, MessageBox, HyperlinkButton, InfoBar,
                            InfoBarPosition, CaptionLabel, RoundMenu, Action)

from ui.ui_home import Ui_Home

APPS_CONFIG_FILE = "apps_config.json"
LINKS_CONFIG_FILE = "links_config.json"
TASKS_CONFIG_FILE = "tasks_config.json"


# ==================== 组件封装区 ====================

class AdaptiveUrlLabel(BodyLabel):
    """ 自适应宽度的 URL 标签 """

    def __init__(self, text="", parent=None):
        super().__init__(parent=parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumWidth(50)
        self.setText(text)

    def setText(self, text):
        self._full_text = text
        self._update_text()

    def resizeEvent(self, event):
        self._update_text()
        super().resizeEvent(event)

    def _update_text(self):
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, Qt.ElideRight, self.width())
        super().setText(elided)


class SquareAppCard(CardWidget):
    """ 自定义正方形应用启动卡片 """
    appClicked = pyqtSignal(str)

    def __init__(self, name, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setFixedSize(86, 86)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        icon = IconWidget(FluentIcon.APPLICATION, self)
        icon.setFixedSize(32, 32)

        label = BodyLabel(name, self)
        label.setAlignment(Qt.AlignCenter)

        if not path:
            self.setToolTip("未配置路径")
            label.setStyleSheet("color: gray;")
        else:
            self.setToolTip(path)

        layout.addWidget(icon, 0, Qt.AlignHCenter)
        layout.addWidget(label, 0, Qt.AlignHCenter)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.path:
            self.appClicked.emit(self.path)


class TaskItemCard(CardWidget):
    """ 带右键交互、横线划掉和【极致色彩美化】的任务卡片 """
    stateChanged = pyqtSignal(bool)
    deleted = pyqtSignal()

    def __init__(self, task_data, parent=None):
        super().__init__(parent)
        self.task_data = task_data
        self.setFixedHeight(44)

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(15, 0, 15, 0)
        self.hBoxLayout.setSpacing(12)

        # 任务前方的图标
        self.iconWidget = IconWidget(self)
        self.iconWidget.setFixedSize(16, 16)

        # 任务文字描述
        self.taskLabel = BodyLabel(self.task_data.get("text", ""), self)

        self.hBoxLayout.addWidget(self.iconWidget)
        self.hBoxLayout.addWidget(self.taskLabel)
        self.hBoxLayout.addStretch(1)

        self.update_ui_state()

    def update_ui_state(self):
        """ 核心美化逻辑：根据状态动态改变图标颜色和字体样式 """
        is_completed = self.task_data.get("completed", False)
        font = self.taskLabel.font()

        # 实例化一个图形着色器，准备给图标上色
        effect = QGraphicsColorizeEffect(self.iconWidget)

        if is_completed:
            self.iconWidget.setIcon(FluentIcon.COMPLETED)
            effect.setColor(QColor("#107C41"))  # 👈 微软经典的完成绿
            font.setStrikeOut(True)
            self.taskLabel.setFont(font)
            self.taskLabel.setStyleSheet("color: #888888;")
        else:
            self.iconWidget.setIcon(FluentIcon.INFO)
            effect.setColor(QColor("#C43E1C"))  # 👈 微软警示橙褐
            font.setStrikeOut(False)
            self.taskLabel.setFont(font)
            self.taskLabel.setStyleSheet("")

            # 将着色效果应用到图标上
        self.iconWidget.setGraphicsEffect(effect)

    def contextMenuEvent(self, event):
        menu = RoundMenu(parent=self)

        complete_action = Action(FluentIcon.COMPLETED, "标记为已完成")
        complete_action.triggered.connect(lambda: self.stateChanged.emit(True))

        uncomplete_action = Action(FluentIcon.INFO, "标记为未完成")
        uncomplete_action.triggered.connect(lambda: self.stateChanged.emit(False))

        delete_action = Action(FluentIcon.DELETE, "删除此任务")
        delete_action.triggered.connect(self.deleted.emit)

        is_completed = self.task_data.get("completed", False)
        if is_completed:
            menu.addAction(uncomplete_action)
        else:
            menu.addAction(complete_action)

        menu.addSeparator()
        menu.addAction(delete_action)

        menu.exec(event.globalPos())


# ==================== 弹窗封装区 ====================

class AddTaskDialog(MessageBoxBase):
    """ 👈 专门为添加任务定制的输入弹窗，彻底解决 viewLayout 报错 """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(350)
        self.titleLabel = SubtitleLabel('新建会话任务', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.task_input = LineEdit(self.widget)
        self.task_input.setPlaceholderText("例如：完成每周技术周报...")
        self.task_input.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self.task_input)

        self.yesButton.setText('添加')
        self.cancelButton.setText('取消')


class AppConfigDialog(MessageBoxBase):
    """ 软件启动项配置弹窗 """

    def __init__(self, saved_apps, parent=None):
        super().__init__(parent)
        self.widget.setFixedSize(620, 420)

        self.titleLabel = SubtitleLabel('配置快捷启动项', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.yesButton.setText('保存配置')
        self.cancelButton.setText('取消')

        self.saved_apps = saved_apps
        self.inputs = []

        self.scrollArea = SmoothScrollArea(self.widget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setStyleSheet("QScrollArea{border: none; background-color: transparent;}")
        self.scrollArea.viewport().setStyleSheet("background-color: transparent;")

        self.scrollContainer = QWidget()
        self.scrollLayout = QVBoxLayout(self.scrollContainer)
        self.scrollLayout.setContentsMargins(0, 5, 15, 5)
        self.scrollLayout.setSpacing(10)
        self.scrollLayout.setAlignment(Qt.AlignTop)

        self.scrollArea.setWidget(self.scrollContainer)
        self.viewLayout.addWidget(self.scrollArea)

        for app in self.saved_apps:
            self.add_app_row(app.get("name", ""), app.get("path", ""))

        if not self.inputs:
            self.add_app_row("", "")

        self.actionLayout = QHBoxLayout()
        self.actionLayout.setContentsMargins(0, 10, 0, 0)
        self.btn_add_row = ToolButton(FluentIcon.ADD, self.widget)
        self.btn_add_row.clicked.connect(lambda: self.add_app_row("", ""))
        self.actionLayout.addWidget(self.btn_add_row, 0, Qt.AlignLeft)
        self.viewLayout.addLayout(self.actionLayout)

    def add_app_row(self, name="", path=""):
        row_widget = QWidget(self.scrollContainer)
        h_layout = QHBoxLayout(row_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        name_input = LineEdit(row_widget)
        name_input.setText(name)
        name_input.setPlaceholderText("应用名称")
        name_input.setFixedWidth(130)

        path_input = LineEdit(row_widget)
        path_input.setText(path)
        path_input.setPlaceholderText("请选择或输入 .exe 绝对路径")

        btn_browse = PushButton("...", row_widget)
        btn_browse.setFixedWidth(40)
        btn_browse.clicked.connect(lambda checked, txt=path_input: self.browse_exe_file(txt))

        btn_delete = ToolButton(FluentIcon.DELETE, row_widget)
        btn_delete.setFixedWidth(36)
        btn_delete.clicked.connect(lambda: self.remove_app_row(row_widget, (name_input, path_input)))

        h_layout.addWidget(name_input)
        h_layout.addWidget(path_input)
        h_layout.addWidget(btn_browse)
        h_layout.addWidget(btn_delete)

        self.scrollLayout.addWidget(row_widget)
        self.inputs.append((name_input, path_input))

    def remove_app_row(self, row_widget, input_pair):
        if input_pair in self.inputs:
            self.inputs.remove(input_pair)
        row_widget.deleteLater()
        self.scrollLayout.removeWidget(row_widget)

    def browse_exe_file(self, target_line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择可执行文件", "C:/", "Executable Files (*.exe)")
        if file_path:
            target_line_edit.setText(file_path)


class LinkConfigDialog(MessageBoxBase):
    """ 常用网址系统入口快捷配置弹窗 """

    def __init__(self, saved_links, parent=None):
        super().__init__(parent)
        self.widget.setFixedSize(620, 420)

        self.titleLabel = SubtitleLabel('配置常用系统入口', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.yesButton.setText('保存配置')
        self.cancelButton.setText('取消')

        self.saved_links = saved_links
        self.inputs = []

        self.scrollArea = SmoothScrollArea(self.widget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setStyleSheet("QScrollArea{border: none; background-color: transparent;}")
        self.scrollArea.viewport().setStyleSheet("background-color: transparent;")

        self.scrollContainer = QWidget()
        self.scrollLayout = QVBoxLayout(self.scrollContainer)
        self.scrollLayout.setContentsMargins(0, 5, 15, 5)
        self.scrollLayout.setSpacing(10)
        self.scrollLayout.setAlignment(Qt.AlignTop)

        self.scrollArea.setWidget(self.scrollContainer)
        self.viewLayout.addWidget(self.scrollArea)

        for link in self.saved_links:
            self.add_link_row(link.get("name", ""), link.get("url", ""))

        if not self.inputs:
            self.add_link_row("", "")

        self.actionLayout = QHBoxLayout()
        self.actionLayout.setContentsMargins(0, 10, 0, 0)
        self.btn_add_row = ToolButton(FluentIcon.ADD, self.widget)
        self.btn_add_row.clicked.connect(lambda: self.add_link_row("", ""))
        self.actionLayout.addWidget(self.btn_add_row, 0, Qt.AlignLeft)
        self.viewLayout.addLayout(self.actionLayout)

    def add_link_row(self, name="", url=""):
        row_widget = QWidget(self.scrollContainer)
        h_layout = QHBoxLayout(row_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        name_input = LineEdit(row_widget)
        name_input.setText(name)
        name_input.setPlaceholderText("系统名称")
        name_input.setFixedWidth(130)

        url_input = LineEdit(row_widget)
        url_input.setText(url)
        url_input.setPlaceholderText("请输入网址 URL (例如 https://...)")

        btn_delete = ToolButton(FluentIcon.DELETE, row_widget)
        btn_delete.setFixedWidth(36)
        btn_delete.clicked.connect(lambda: self.remove_link_row(row_widget, (name_input, url_input)))

        h_layout.addWidget(name_input)
        h_layout.addWidget(url_input)
        h_layout.addWidget(btn_delete)

        self.scrollLayout.addWidget(row_widget)
        self.inputs.append((name_input, url_input))

    def remove_link_row(self, row_widget, input_pair):
        if input_pair in self.inputs:
            self.inputs.remove(input_pair)
        row_widget.deleteLater()
        self.scrollLayout.removeWidget(row_widget)


# ==================== 主页面业务逻辑层 ====================

class HomeInterface(QWidget):
    """ 首页逻辑层 """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Home()
        self.ui.setupUi(self)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()

        # 👈 核心美化：把主界面任务区的大标题图标强行染成微软蓝
        title_effect = QGraphicsColorizeEffect(self)
        title_effect.setColor(QColor("#0078D4"))
        self.ui.taskIcon.setGraphicsEffect(title_effect)

        # --- 任务清单数据与事件 ---
        self.saved_tasks = []
        self.load_tasks_config()
        self.ui.btn_add_task.clicked.connect(self.show_add_task_dialog)

        # --- 软件配置数据 ---
        self.saved_apps = []
        self.load_apps_config()
        self.ui.btn_add_app.clicked.connect(self.show_config_dialog)

        # --- 链接配置数据 ---
        self.saved_links = []
        self.load_links_config()
        self.ui.btn_config_links.clicked.connect(self.show_links_config_dialog)

    def update_time(self):
        current_time = QDateTime.currentDateTime()
        self.ui.lbl_time.setText(current_time.toString("hh:mm:ss"))
        self.ui.lbl_date.setText(current_time.toString("yyyy年MM月dd日 dddd"))

    # ================= 任务清单核心逻辑 =================
    def load_tasks_config(self):
        if os.path.exists(TASKS_CONFIG_FILE):
            try:
                with open(TASKS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.saved_tasks = json.load(f)
            except Exception:
                self.saved_tasks = []
        else:
            self.saved_tasks = [
                {"text": "全军出击，誓死保卫鸽鸽！！", "completed": True},
                {"text": "检查 Oracle RAC 归档日志空间", "completed": False},
                {"text": "上传并部署新的工作台版本", "completed": False}
            ]
        self.refresh_tasks_ui()

    def save_tasks_to_local(self):
        try:
            with open(TASKS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.saved_tasks, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存任务数据失败: {e}")

    def refresh_tasks_ui(self):
        layout = self.ui.tasksContainerLayout

        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for index, task in enumerate(self.saved_tasks):
            card = TaskItemCard(task, self.ui.taskScrollContainer)
            card.stateChanged.connect(lambda state, i=index: self.update_task_state(i, state))
            card.deleted.connect(lambda i=index: self.delete_task(i))
            layout.addWidget(card)

    def update_task_state(self, index, is_completed):
        if 0 <= index < len(self.saved_tasks):
            self.saved_tasks[index]["completed"] = is_completed
            self.save_tasks_to_local()
            self.refresh_tasks_ui()

    def delete_task(self, index):
        if 0 <= index < len(self.saved_tasks):
            del self.saved_tasks[index]
            self.save_tasks_to_local()
            self.refresh_tasks_ui()

    def show_add_task_dialog(self):
        """ 👈 修复后的调用方式，调起我们全新重写的 AddTaskDialog """
        w = AddTaskDialog(self.window())

        if w.exec() and w.task_input.text().strip():
            new_text = w.task_input.text().strip()
            self.saved_tasks.append({"text": new_text, "completed": False})
            self.save_tasks_to_local()
            self.refresh_tasks_ui()

    # ================= 常用系统网址入口读写 =================
    def load_links_config(self):
        if os.path.exists(LINKS_CONFIG_FILE):
            try:
                with open(LINKS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.saved_links = json.load(f)
            except Exception:
                self.saved_links = []
        else:
            self.saved_links = [
                {"name": "Oracle 数据库监控控制台", "url": "https://172.16.1.44:1521"},
                {"name": "ESXi 虚拟化管理后台", "url": "https://esxi.domain.com"},
                {"name": "泛微 OA 系统", "url": "https://oa.weaver.com.cn"}
            ]
        self.refresh_links_ui()

    def refresh_links_ui(self):
        layout = self.ui.linksContainerLayout

        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for link_info in self.saved_links:
            name = link_info.get("name", "未命名网址")
            url = link_info.get("url", "")

            row_item = QWidget(self.ui.linkScrollContainer)
            row_layout = QHBoxLayout(row_item)
            row_layout.setContentsMargins(0, 0, 10, 0)
            row_layout.setSpacing(12)

            link_btn = HyperlinkButton(url, name, row_item)
            link_btn.setToolTip(url)

            url_label = AdaptiveUrlLabel(url, row_item)
            url_label.setStyleSheet("color: #888888; font-size: 13px;")
            url_label.setToolTip(url)

            copy_btn = ToolButton(FluentIcon.COPY, row_item)
            copy_btn.setToolTip("复制网址")
            copy_btn.clicked.connect(lambda checked, text_to_copy=url: self.copy_link_to_clipboard(text_to_copy))

            row_layout.addWidget(link_btn)
            row_layout.addWidget(url_label, 1)
            row_layout.addWidget(copy_btn)

            layout.addWidget(row_item)

    def copy_link_to_clipboard(self, text):
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            InfoBar.success(
                title='复制成功',
                content=f'网址链接 已顺利复制到您的系统剪贴板！',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.window()
            )
        except Exception as e:
            print(f"复制失败: {e}")

    def show_links_config_dialog(self):
        w = LinkConfigDialog(self.saved_links, self.window())
        if w.exec():
            new_links = []
            for name_in, url_in in w.inputs:
                name_text = name_in.text().strip()
                url_text = url_in.text().strip()
                if name_text:
                    new_links.append({"name": name_text, "url": url_text})

            self.saved_links = new_links
            try:
                with open(LINKS_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.saved_links, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"网址保存在本地失败: {e}")

            self.refresh_links_ui()

    # ================= 软件快捷启动读写 =================
    def load_apps_config(self):
        if os.path.exists(APPS_CONFIG_FILE):
            try:
                with open(APPS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.saved_apps = json.load(f)
            except Exception:
                self.saved_apps = []
        else:
            self.saved_apps = [
                {"name": "微信", "path": ""},
                {"name": "Everything", "path": ""}
            ]
        self.refresh_apps_ui()

    def refresh_apps_ui(self):
        layout = self.ui.appsContainerLayout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        columns = 4
        for i, app_info in enumerate(self.saved_apps):
            name = app_info.get("name", "未命名")
            path = app_info.get("path", "")

            card = SquareAppCard(name, path, self.ui.appLaunchCard)
            card.appClicked.connect(self.launch_app)

            row = i // columns
            col = i % columns
            layout.addWidget(card, row, col)

    def launch_app(self, path):
        if not path or not os.path.exists(path):
            w = MessageBox("提示", "找不到指定的程序文件，请检查路径是否正确！", self.window())
            w.exec()
            return
        try:
            subprocess.Popen(path, shell=True)
        except Exception as e:
            print(f"启动程序失败: {e}")

    def show_config_dialog(self):
        w = AppConfigDialog(self.saved_apps, self.window())
        if w.exec():
            new_config = []
            for name_in, path_in in w.inputs:
                name_text = name_in.text().strip()
                path_text = path_in.text().strip().replace("\\", "/")
                if name_text:
                    new_config.append({"name": name_text, "path": path_text})

            self.saved_apps = new_config
            try:
                with open(APPS_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.saved_apps, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"保存在本地失败: {e}")

            self.refresh_apps_ui()