# coding:utf-8
import sys, os, time, ssl, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pymysql

from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer, QUrl, pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                             QAbstractItemView, QHeaderView, QTableWidgetItem, QStackedWidget, QScrollArea)
from PyQt5.QtWebEngineWidgets import QWebEngineView

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

from qfluentwidgets import (InfoBar, TableWidget, PushButton, MessageBoxBase,
                            SubtitleLabel, LineEdit, Dialog, ProgressBar, ToolButton, FluentIcon)
from config.config import SERVER_DB_CONFIG
from ui.ui_esxi import Ui_Esxi




# ================= 通信类 =================
class Communicate(QObject):
    update_sync_status = pyqtSignal(str, bool)
    update_progress = pyqtSignal(int)


# ================= 弹窗对话框 =================
class HostEditDialog(MessageBoxBase):
    """ Fluent 风格的新增/编辑主机弹窗 """

    def __init__(self, parent=None, host=None):
        super().__init__(parent)
        self.widget.setMinimumWidth(350)
        self.titleLabel = SubtitleLabel('服务器节点配置', self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        self.ip_input = LineEdit(self.widget)
        self.ip_input.setPlaceholderText("主机 IP 地址")
        self.viewLayout.addWidget(self.ip_input)

        self.user_input = LineEdit(self.widget)
        self.user_input.setPlaceholderText("用户名")
        self.viewLayout.addWidget(self.user_input)

        self.pwd_input = LineEdit(self.widget)
        self.pwd_input.setPlaceholderText("密码")
        self.pwd_input.setEchoMode(LineEdit.Password)
        self.viewLayout.addWidget(self.pwd_input)

        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')

        if host:
            self.ip_input.setText(host["host_ip"])
            self.user_input.setText(host["username"])
            self.pwd_input.setText(host["pwd"])
            self.ip_input.setEnabled(False)  # 编辑模式下禁止修改 IP

    def get_data(self):
        return {
            "host_ip": self.ip_input.text().strip(),
            "username": self.user_input.text().strip(),
            "pwd": self.pwd_input.text().strip()
        }


# ================= 具体主机的监控 Tab =================
class HostTabWidget(QWidget):
    refresh_vm_table = pyqtSignal()
    update_host_ui = pyqtSignal(object, object)

    def __init__(self, host_ip, credentials, parent=None):
        super().__init__(parent)
        self.host_ip = host_ip
        self.credentials = credentials
        self.si = None
        self.content = None
        self.current_host_vms = []
        self.is_browser_loaded = False

        self.init_ui()

        self.update_host_ui.connect(self._update_ui_data)
        self.refresh_vm_table.connect(self._auto_refresh_vm_status)

        threading.Thread(target=self.fetch_data_thread, daemon=True).start()

        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.setInterval(5000)
        self.auto_refresh_timer.timeout.connect(self._auto_refresh_vm_status)
        self.auto_refresh_timer.start()

    def _create_metric_card(self, title):
        """ 👈 核心美化 1：生成带进度条的精美数据卡片 """
        frame = QFrame()
        frame.setStyleSheet("background: #ffffff; border: 1px solid #EBEBEB; border-radius: 8px;")
        frame.setFixedHeight(65)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(15, 10, 15, 10)

        header_lay = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #555; font-size: 13px; font-weight: bold; border: none;")
        val_lbl = QLabel("加载中...")
        val_lbl.setStyleSheet("color: #0078D4; font-size: 13px; font-weight: bold; border: none;")

        header_lay.addWidget(title_lbl)
        header_lay.addStretch()
        header_lay.addWidget(val_lbl)

        bar = ProgressBar()
        bar.setFixedHeight(4)

        lay.addLayout(header_lay)
        lay.addWidget(bar)
        return frame, val_lbl, bar

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack)

        # --- 1. 仪表盘页面 ---
        dashboard_widget = QWidget()
        self.mon_layout = QVBoxLayout(dashboard_widget)
        self.mon_layout.setSpacing(16)
        self.mon_layout.setContentsMargins(0, 0, 0, 0)

        # 头部标题
        header_lay = QHBoxLayout()
        self.title_lbl = QLabel(f"🖥️ ESXi 节点 - {self.host_ip}")
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        self.host_info_lbl = QLabel("正在连接服务器获取信息...")
        self.host_info_lbl.setStyleSheet("color: #888;")
        header_lay.addWidget(self.title_lbl)
        header_lay.addStretch()
        header_lay.addWidget(self.host_info_lbl)
        self.mon_layout.addLayout(header_lay)

        # 👈 核心美化 2：恢复 CPU 和 内存卡片
        res_row = QHBoxLayout()
        self.cpu_card, self.cpu_val, self.cpu_bar = self._create_metric_card("CPU 实时负载")
        self.mem_card, self.mem_val, self.mem_bar = self._create_metric_card("内存消耗容量")
        res_row.addWidget(self.cpu_card)
        res_row.addWidget(self.mem_card)
        self.mon_layout.addLayout(res_row)

        # 存储状态区
        self.storage_layout = QHBoxLayout()
        self.storage_layout.setSpacing(12)
        self.mon_layout.addLayout(self.storage_layout)

        # 虚拟机列表 (使用 Fluent 的 TableWidget)
        self.vm_table = TableWidget(dashboard_widget)
        self.vm_table.setColumnCount(8)
        self.vm_table.setHorizontalHeaderLabels(
            ["#", "虚拟机名称", "操作系统", "电源状态", "IP 地址", "快照", "资源配置", "控制"])
        self.vm_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.vm_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.vm_table.setShowGrid(False)
        self.vm_table.setAlternatingRowColors(True)

        # 👈 核心修复 3：智能列宽，保证内容完整显示
        header = self.vm_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)  # 绝大部分列根据内容自动撑开
        #header.setSectionResizeMode(1, QHeaderView.Stretch)  # 虚拟机名称列：自动拉伸占满剩余空间
        self.vm_table.setMinimumWidth(200)

        self.mon_layout.addWidget(self.vm_table)

        self.jump_btn = PushButton("🚀 进入 vSphere WEB 管理控制台", dashboard_widget)
        self.jump_btn.clicked.connect(self.go_to_web)
        self.mon_layout.addWidget(self.jump_btn)

        self.stack.addWidget(dashboard_widget)

        # --- 2. WEB 控制台页面 ---
        self.web_page = QWidget()
        web_lay = QVBoxLayout(self.web_page)
        web_lay.setContentsMargins(0, 0, 0, 0)

        nav = QHBoxLayout()
        btn_back = PushButton("⬅ 返回仪表盘 (保持后台连接)", self.web_page)
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        nav.addWidget(btn_back)
        nav.addStretch()

        self.browser = QWebEngineView()
        self.browser.page().profile().setHttpAcceptLanguage("zh-CN,zh;q=0.9")
        self.browser.page().certificateError = lambda err: True
        self.browser.loadFinished.connect(self.handle_auto_login)

        web_lay.addLayout(nav)
        web_lay.addWidget(self.browser)
        self.stack.addWidget(self.web_page)

    def fetch_data_thread(self):
        try:
            context = ssl._create_unverified_context()
            self.si = SmartConnect(host=self.host_ip, user=self.credentials['username'], pwd=self.credentials['pwd'],
                                   sslContext=context)
            self.content = self.si.RetrieveContent()
            host = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.HostSystem], True).view[0]
            self._reload_vms_internal()
            self.update_host_ui.emit(host, self.content)
        except Exception as e:
            InfoBar.warning('提示', 'Connection failed for {self.host_ip}: {e}"', parent=self.window(), duration=2000)
            #print(f"Connection failed for {self.host_ip}: {e}")

    def _reload_vms_internal(self):
        if not self.content: return
        try:
            view = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.VirtualMachine], True)
            vm_list = []
            for vm in view.view:
                vm_list.append({
                    "name": vm.name,
                    "ip": vm.guest.ipAddress or "-",
                    "power": vm.runtime.powerState,
                    "os": vm.config.guestFullName if vm.config else "Unknown",
                    "cpu": vm.config.hardware.numCPU if vm.config else 0,
                    "mem": vm.config.hardware.memoryMB if vm.config else 0,
                    "vm_obj": vm
                })
            view.Destroy()
            self.current_host_vms = vm_list
        except:
            pass

    def _auto_refresh_vm_status(self):
        if not self.si: return
        self._reload_vms_internal()
        self.update_vm_table(self.current_host_vms)

    @pyqtSlot(object, object)
    def _update_ui_data(self, host, content):
        self.host_info_lbl.setText(
            f"OS 版本: {host.config.product.version}  |  已运行: {host.summary.quickStats.uptime // 3600} 小时")

        cu, ct = host.summary.quickStats.overallCpuUsage / 1000, (
                    host.hardware.cpuInfo.hz * host.hardware.cpuInfo.numCpuCores) / 10 ** 9
        mu, mt = host.summary.quickStats.overallMemoryUsage / 1024, host.hardware.memorySize / 1024 ** 3

        # 更新 CPU / 内存 卡片进度
        self.cpu_val.setText(f"{cu:.1f} / {ct:.1f} GHz")
        self.cpu_bar.setValue(int((cu / ct) * 100) if ct > 0 else 0)

        self.mem_val.setText(f"{mu:.1f} / {mt:.1f} GB")
        self.mem_bar.setValue(int((mu / mt) * 100) if mt > 0 else 0)

        # 刷新存储 (恢复小卡片设计)
        while self.storage_layout.count():
            item = self.storage_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for ds in host.datastore:
            try:
                sum_ = ds.summary
                u, t = (sum_.capacity - sum_.freeSpace) / 1024 ** 3, sum_.capacity / 1024 ** 3
                ds_card, ds_val, ds_bar = self._create_metric_card(f"💾 {sum_.name}")
                ds_val.setText(f"{u:.1f}G / {t:.1f}G")
                ds_bar.setValue(int((u / t) * 100) if t > 0 else 0)
                self.storage_layout.addWidget(ds_card)
            except:
                continue
        self.storage_layout.addStretch()

        self.update_vm_table(self.current_host_vms)

    def update_vm_table(self, vms):
        self.vm_table.setRowCount(len(vms))
        for i, vm in enumerate(vms):
            self.vm_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.vm_table.setItem(i, 1, QTableWidgetItem(vm["name"]))
            self.vm_table.setItem(i, 2, QTableWidgetItem(vm["os"]))

            is_on = "poweredOn" in str(vm["power"])
            st_item = QTableWidgetItem("🟢 运行中" if is_on else "⚪ 已停机")
            st_item.setForeground(QColor("#107C41") if is_on else QColor("#888888"))
            self.vm_table.setItem(i, 3, st_item)

            self.vm_table.setItem(i, 4, QTableWidgetItem(vm["ip"]))
            self.vm_table.setItem(i, 5, QTableWidgetItem("-"))  # 快照暂无数据
            self.vm_table.setItem(i, 6, QTableWidgetItem(f'{vm["cpu"]} 核 / {vm["mem"] // 1024} GB'))

            # 注入操作按钮组件
            self.vm_table.setCellWidget(i, 7, self.create_vm_actions(vm["vm_obj"], vm["power"]))

    def create_vm_actions(self, vm, state):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        is_powered_on = (state == vim.VirtualMachinePowerState.poweredOn)

        # 👈 核心美化 4：使用极其优雅的 FluentIcon 替换原来丑陋的文字按钮
        btn_configs = [
            ("启动", FluentIcon.PLAY_SOLID, not is_powered_on, "on"),
            ("关闭", FluentIcon.POWER_BUTTON, is_powered_on, "off"),
            ("重启", FluentIcon.SYNC, is_powered_on, "reset"),
            ("挂起", FluentIcon.PAUSE_BOLD, is_powered_on, "suspend")
        ]

        for tip, ic, enabled, op in btn_configs:
            b = ToolButton(ic, w)
            b.setFixedSize(32, 32)
            b.setToolTip(f"点击 {tip}")
            b.setEnabled(enabled)
            b.clicked.connect(lambda _, a=op, v=vm, btn=b: self.vm_power_task(v, a, btn))
            lay.addWidget(b)

        lay.addStretch()
        return w

    def vm_power_task(self, vm, action, btn):
        title_map = {"on": "启动", "off": "关闭", "reset": "重启", "suspend": "挂起"}
        w = Dialog("确认操作", f"请确认是否要【{title_map[action]}】该虚拟机？", self.window())
        if w.exec():
            threading.Thread(target=self._vm_power_worker, args=(vm, action), daemon=True).start()

    def _vm_power_worker(self, vm, action):
        try:
            if action == "on":
                task = vm.PowerOnVM_Task()
            elif action == "off":
                task = vm.PowerOffVM_Task()
            elif action == "reset":
                task = vm.ResetVM_Task()
            elif action == "suspend":
                task = vm.SuspendVM_Task()
            while task.info.state in [vim.TaskInfo.State.running, vim.TaskInfo.State.queued]:
                time.sleep(0.5)
            self.refresh_vm_table.emit()
        except Exception as e:
            print(f"VM Power Error: {e}")

    def go_to_web(self):
        self.stack.setCurrentIndex(1)
        if not self.is_browser_loaded:
            url = f"https://{self.host_ip}/ui/"
            self.browser.setUrl(QUrl(url))
            self.is_browser_loaded = True

    def handle_auto_login(self, success):
        if not success: return
        current_url = self.browser.url().toString()
        if "/ui/#/login" in current_url or "/ui/" in current_url:
            js_code = f"""
            (function() {{
                var u = document.querySelector('input[name="username"], #username');
                var p = document.querySelector('input[name="password"], #password');
                var b = document.querySelector('button[type="submit"], #submit, .btn-primary');
                if (u && p) {{
                    u.value = "{self.credentials['username']}"; u.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    p.value = "{self.credentials['pwd']}"; p.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    setTimeout(function() {{ if (b) b.click(); }}, 800);
                }}
            }})();
            """
            QTimer.singleShot(1500, lambda: self.browser.page().runJavaScript(js_code))

    def highlight_vm(self, vm_name):
        self.stack.setCurrentIndex(0)
        for row in range(self.vm_table.rowCount()):
            item = self.vm_table.item(row, 1)
            if item and vm_name.lower() in item.text().lower():
                self.vm_table.selectRow(row)
                self.vm_table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                break

    def closeEvent(self, event):
        if self.si:
            try:
                Disconnect(self.si)
            except:
                pass
        event.accept()


# ================= 主界面管理器 =================
class EsxiInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Esxi()
        self.ui.setupUi(self)
        self.setObjectName("Test Interface")  # 保持原名以便路由生效

        self.host_map = {}
        self.all_vms_cache = []
        self.all_vms_loaded = False

        self.comm = Communicate()
        self.comm.update_sync_status.connect(self._handle_sync_status)
        self.comm.update_progress.connect(self._handle_progress)

        # 事件绑定
        self.load_hosts()
        self.ui.btn_add.clicked.connect(self.add_host)
        self.ui.btn_edit.clicked.connect(self.edit_host)
        self.ui.btn_del.clicked.connect(self.delete_host)
        self.ui.list_widget.itemClicked.connect(self.on_host_clicked)
        self.ui.btn_sync.clicked.connect(self.load_all_vms_index)

        # 实时搜索绑定
        self.ui.search_input.textChanged.connect(self.exec_search)
        self.ui.btn_search.clicked.connect(self.exec_search)

        self.ui.tabs.tabCloseRequested.connect(self.close_tab)
    def load_hosts(self):
        try:
            conn = pymysql.connect(**SERVER_DB_CONFIG)
            with conn.cursor() as cursor:
                cursor.execute("SELECT host_ip, username, pwd FROM esxi_host")
                for row in cursor.fetchall():
                    self.ui.list_widget.addItem(row['host_ip'])
                    self.host_map[row['host_ip']] = row
            conn.close()
        except Exception as e:
            InfoBar.error('数据库连接失败', str(e), parent=self.window())

    def on_host_clicked(self, item):
        ip = item.text()
        for i in range(self.ui.tabs.count()):
            widget = self.ui.tabs.widget(i)
            if isinstance(widget, HostTabWidget) and widget.host_ip == ip:
                self.ui.tabs.setCurrentIndex(i)
                return

        creds = self.host_map.get(ip)
        if not creds: return

        self.ui.tabs.setCursor(Qt.WaitCursor)
        new_tab = HostTabWidget(ip, creds, self)
        index = self.ui.tabs.addTab(new_tab, ip)
        self.ui.tabs.setCurrentIndex(index)
        self.ui.tabs.setCursor(Qt.ArrowCursor)

    def close_tab(self, index):
        widget = self.ui.tabs.widget(index)
        if isinstance(widget, HostTabWidget):
            widget.close()
        self.ui.tabs.removeTab(index)

    def add_host(self):
        dlg = HostEditDialog(self.window())
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("INSERT INTO esxi_host(host_ip, username, pwd) VALUES(%s,%s,%s)",
                              (data["host_ip"], data["username"], data["pwd"]))
                conn.commit()
                conn.close()
                self.ui.list_widget.addItem(data["host_ip"])
                self.host_map[data["host_ip"]] = data
                InfoBar.success('成功', '节点添加成功', parent=self.window())
            except Exception as e:
                InfoBar.error('失败', str(e), parent=self.window())

    def edit_host(self):
        item = self.ui.list_widget.currentItem()
        if not item: return
        ip = item.text()
        dlg = HostEditDialog(self.window(), self.host_map[ip])
        if dlg.exec():
            data = dlg.get_data()
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("UPDATE esxi_host SET username=%s, pwd=%s WHERE host_ip=%s",
                              (data["username"], data["pwd"], ip))
                conn.commit()
                conn.close()
                self.host_map[ip].update(data)
                InfoBar.success('成功', '节点更新成功', parent=self.window())
            except Exception as e:
                InfoBar.error('失败', str(e), parent=self.window())

    def delete_host(self):
        item = self.ui.list_widget.currentItem()
        if not item: return
        ip = item.text()
        w = Dialog("确认删除", f"确定删除服务器 {ip}？", self.window())
        if w.exec():
            try:
                conn = pymysql.connect(**SERVER_DB_CONFIG)
                with conn.cursor() as c:
                    c.execute("DELETE FROM esxi_host WHERE host_ip=%s", (ip,))
                conn.commit()
                conn.close()
                self.ui.list_widget.takeItem(self.ui.list_widget.row(item))
                del self.host_map[ip]
                InfoBar.success('成功', '节点已删除', parent=self.window())
            except Exception as e:
                InfoBar.error('失败', str(e), parent=self.window())

    # ================= 索引与搜索 =================
    def load_all_vms_index(self):
        self.comm.update_sync_status.emit("⏳ 同步中...", False)
        self.ui.sync_progress.setValue(0)
        self.ui.sync_progress.show()

        def fetch_single_host(ip, creds):
            vms = []
            try:
                context = ssl._create_unverified_context()
                si = SmartConnect(host=ip, user=creds['username'], pwd=creds['pwd'], sslContext=context)
                content = si.RetrieveContent()
                view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
                for vm in view.view:
                    vms.append({"name": vm.name, "ip": (vm.guest.ipAddress or "").lower(), "host": ip})
                Disconnect(si)
            except:
                pass
            return vms

        def thread_manager():
            all_results = []
            host_ips = list(self.host_map.keys())
            total_tasks = len(host_ips)
            if total_tasks == 0:
                self.comm.update_sync_status.emit("无主机", True)
                return

            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {executor.submit(fetch_single_host, ip, self.host_map[ip]): ip for ip in host_ips}
                completed_count = 0
                for future in as_completed(futures):
                    all_results.extend(future.result())
                    completed_count += 1
                    self.comm.update_progress.emit(int((completed_count / total_tasks) * 100))

            self.all_vms_cache = all_results
            self.all_vms_loaded = True
            self.comm.update_sync_status.emit(f"✅ 已同步 {len(all_results)} VM", True)
            time.sleep(1.5)
            self.comm.update_progress.emit(-1)

        threading.Thread(target=thread_manager, daemon=True).start()

    def _handle_progress(self, val):
        if val == -1:
            self.ui.sync_progress.hide()
        else:
            self.ui.sync_progress.setValue(val)

    def _handle_sync_status(self, text, enabled):
        self.ui.btn_sync.setText(text)
        self.ui.btn_sync.setEnabled(enabled)

    def exec_search(self):
        query = self.ui.search_input.text().strip().lower()
        if not query: return
        if not self.all_vms_loaded:
            InfoBar.warning("提示", "请先点击同步索引按钮获取数据", parent=self.window())
            return

        found_vm = next((vm for vm in self.all_vms_cache if query == vm["name"].lower()), None)
        if not found_vm:
            found_vm = next((vm for vm in self.all_vms_cache if query in vm["name"].lower() or query in vm["ip"]), None)

        if found_vm:
            items = self.ui.list_widget.findItems(found_vm["host"], Qt.MatchExactly)
            if items:
                self.ui.list_widget.setCurrentItem(items[0])
                self.on_host_clicked(items[0])
                QTimer.singleShot(800, lambda: self.highlight_in_current_tab(found_vm["name"]))
        else:
            InfoBar.info("结果", "未找到匹配的虚拟机", parent=self.window())

    def highlight_in_current_tab(self, vm_name):
        current = self.ui.tabs.currentWidget()
        if isinstance(current, HostTabWidget):
            current.highlight_vm(vm_name)