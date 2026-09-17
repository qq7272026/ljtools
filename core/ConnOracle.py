import oracledb

class ConnOracle:
    def __init__(self, username, password, host, port, service_name):
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.service_name = service_name
        self.connection = None
        self.cursor = None

    # ⭐ 新增内部静态方法：处理类型转换
    @staticmethod
    def _output_type_handler(cursor, name, default_type, size, precision, scale):
        # 如果发现返回类型是 CLOB，则将其作为 LONG_STRING 处理（自动转为字符串）
        if default_type == oracledb.CLOB:
            return cursor.var(oracledb.LONG_STRING, arraysize=cursor.arraysize)
        # 如果是 BLOB，转为 LONG_BINARY
        if default_type == oracledb.BLOB:
            return cursor.var(oracledb.LONG_BINARY, arraysize=cursor.arraysize)
    def connect(self):
        try:
            dsn = oracledb.makedsn(self.host, self.port, service_name=self.service_name)
            # ⭐ 核心修复：如果是 sys 用户，自动附加 SYSDBA 权限
            if self.username.lower() == 'sys':
                self.connection = oracledb.connect(user=self.username, password=self.password, dsn=dsn, mode=oracledb.SYSDBA)
            else:
                self.connection = oracledb.connect(user=self.username, password=self.password, dsn=dsn)
            return "successful"
        except oracledb.DatabaseError as e:
            # Handle any potential database errors
            if str(e)=="ORA-01017: invalid username/password; logon denied":
                return "账号密码错误"
            else:
                return f"Oracle connection failed: {str(e)}"

    def connectorcl(self):
        try:
            dsn = oracledb.makedsn(self.host, self.port, service_name=self.service_name)
            # ⭐ 核心修复：同样为这个方法增加 sys 用户的判断
            if self.username.lower() == 'sys':
                self.connection = oracledb.connect(user=self.username, password=self.password, dsn=dsn, mode=oracledb.SYSDBA)
            else:
                self.connection = oracledb.connect(user=self.username, password=self.password, dsn=dsn)
            # ⭐ 核心：在 connection 上绑定类型处理器
            self.connection.outputtypehandler = self._output_type_handler
            self.cursor = self.connection.cursor()
        except oracledb.Error as error:
            print(f"Error: {error}")

    def disconnect(self):
        """ 安全断开连接，忽略已断开连接引发的 DPY-1001 异常 """
        try:
            if hasattr(self, 'cursor') and self.cursor:
                self.cursor.close()
        except Exception:
            pass  # 如果游标已经关闭或连接已死，直接忽略

        try:
            if hasattr(self, 'connection') and self.connection:
                self.connection.close()
        except Exception:
            pass  # 如果连接已经被强制掐断，直接忽略

    def execute_query(self, query, params=None):
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            self.connection.commit()
        except oracledb.Error as error:
            print(f"{error}")
    def fetch_all(self, query, params=None):
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor.fetchall()
        except oracledb.Error as error:
            print(f"Error: {error}")
            return None
    def fetch_one(self, query, params=None):
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor.fetchone()
        except oracledb.Error as error:
            print(f"Error: {error}")
            return None
    def execute_update(self, table, data, condition):
        set_clause = ', '.join([f"{key} = :{key}" for key in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {condition}"
        self.execute_query(query, data)

    def execute_delete(self, table, condition):
        query = f"DELETE FROM {table} WHERE {condition}"
        self.execute_query(query)

    def execute_insert(self, table, data):
        columns = ', '.join(data.keys())
        placeholders = ', '.join([f":{key}" for key in data.keys()])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        self.execute_query(query, data)
