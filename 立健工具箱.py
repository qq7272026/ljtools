# coding:utf-8
import sys,os,json,hashlib,base64,warnings

# 屏蔽警告
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", module="qfluentwidgets")

os.environ["QT_API"] = "PyQt5"

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget
from qfluentwidgets import MessageBox

# 【提速关键 1】顶部只导入轻量的 login_ui，绝对不要导入 main_ui
from ui.login_ui import Ui_Form
from config.config import LOGIN_DB_CONFIG

CONFIG_FILE = "config.json"


class LoginWindow(QWidget):
    login_successful = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.login = Ui_Form()
        self.login.setupUi(self)
        self.login.btn_login.clicked.connect(self.check_login)
        self.load_credentials()
        self.lastname=None

    def check_login(self):
        # 【提速关键 2】延迟加载 Oracle 驱动
        import oracledb
        from pathlib import Path
        # 1. 精确获取项目下 client_1/bin 的绝对路径
        # 假设这段代码在 ljtoolbox/core/ConnOracle.py 中
        core_dir = Path(__file__).resolve().parent
        oracle_home_dir = core_dir/"core" / "client_1"
        oracle_bin_dir = oracle_home_dir / "bin"  # 必须精确到 bin 目录

        # 将路径转换为纯字符串
        bin_path_str = str(oracle_bin_dir)

        # ================= 核心修复区 =================

        # 修复A：将项目中的 bin 目录强制推入当前 Python 进程的 PATH 最前面
        # 这能解决 oci.dll 加载其他衍生 DLL 时的路径寻址问题
        os.environ["PATH"] = bin_path_str + os.pathsep + os.environ.get("PATH", "")

        # 修复B：解决 Python 3.8+ 在 Windows 下更严格的 DLL 加载安全策略
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(bin_path_str)

        # 修复C：确保时区和错误信息文件能被正确找到
        os.environ["ORACLE_HOME"] = str(oracle_home_dir)

        # ==============================================

        try:
            # 2. 初始化客户端
            oracledb.init_oracle_client(lib_dir=bin_path_str)
            print(f"✅ Oracle 客户端初始化成功！加载路径: {bin_path_str}")
        except Exception as e:
            print(f"❌ Oracle 客户端初始化失败: {e}")
        #oracledb.init_oracle_client(lib_dir=r"D:\app\client\zpc\product\19.0.0\client_1\bin")
        username = self.login.l_username.text().strip()
        raw_password = self.login.l_passwd.text()

        if not username or not raw_password:
            self.show_error("请输入账号和密码！")
            return

        md5_pwd = hashlib.md5(raw_password.encode('utf-8')).hexdigest().upper()
        try:
            conn = oracledb.connect(**LOGIN_DB_CONFIG)
            cursor = conn.cursor()

            sql = "SELECT id, lastname FROM hrmresource WHERE loginid = :1 AND password = :2"
            cursor.execute(sql, (username, md5_pwd))
            user_record = cursor.fetchone()
            cursor.close()
            conn.close()

            if user_record:
                lastname = user_record[1]
                if self.login.chb_remember.isChecked():
                    self.save_credentials(username, raw_password)
                else:
                    self.clear_credentials()
                user_info = {"loginid": username, "lastname": lastname}
                self.login_successful.emit(user_info)
            else:
                self.show_error("用户名或密码错误，请重试！")
        except Exception as e:
            self.show_error(f"数据库连接或查询失败：\n{str(e)}")

    def show_error(self, message):
        w = MessageBox("提示", message, self)
        w.yesButton.setText("确定")
        w.cancelButton.hide()
        w.exec()

    def save_credentials(self, username, password):
        try:
            b64_pwd = base64.b64encode(password.encode('utf-8')).decode('utf-8')
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"username": username, "password": b64_pwd}, f)
        except Exception:
            pass

    def load_credentials(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.login.l_username.setText(data.get("username", ""))
                    b64_pwd = data.get("password", "")
                    if b64_pwd:
                        raw_pwd = base64.b64decode(b64_pwd.encode('utf-8')).decode('utf-8')
                        self.login.l_passwd.setText(raw_pwd)
                    self.login.chb_remember.setChecked(True)
            except Exception:
                self.clear_credentials()

    def clear_credentials(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)


# ================= 全局调度逻辑 =================
login_w = None
main_w = None


def switch_to_main(user_info):
    global main_w, login_w

    # 【提速关键 3】核心：只有在密码输入正确、点击登录后，才去加载主界面和那些臃肿的包！
    from main import Window
    main_w = Window(user_info)
    main_w.set_user_menu(user_info["lastname"])
    main_w.logout_signal.connect(switch_to_login)

    main_w.show()
    login_w.close()


def switch_to_login():
    global main_w, login_w

    # 【修复】：判断是否勾选了“记住密码”
    # 如果没有勾选，退出登录时顺手把密码框清空
    if not login_w.login.chb_remember.isChecked():
        login_w.login.l_passwd.clear()

    login_w.show()
    if main_w:
        main_w.close()
        main_w.deleteLater()
        main_w = None


# ================= 程序入口 =================
if __name__ == '__main__':
    # 忽略证书错误（解决 ERR_CERT_AUTHORITY_INVALID）
    sys.argv.append("--ignore-certificate-errors")
    # 如果还需要禁用沙盒（某些系统环境下 WebEngine 需要）
    sys.argv.append("--no-sandbox")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    # 👇【新增这一行】必须在 QApplication 实例化之前开启 OpenGL 上下文共享
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)

    # 直接弹出登录框
    login_w = LoginWindow()
    login_w.login_successful.connect(switch_to_main)
    login_w.show()

    sys.exit(app.exec_())