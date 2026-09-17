# 保持你的原数据库配置
import pymysql

SERVER_DB_CONFIG = {
    "host": "192.168.0.185",
    "user": "root",
    "password": "ljyyc6791048",  # 请填写你的真实密码
    "database": "ljtools",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}
LOGIN_DB_CONFIG={
    "user":"ecology",
    "password":"ecology",
    "dsn":"172.16.1.44:1521/orcl"
}