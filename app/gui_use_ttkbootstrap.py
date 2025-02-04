import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from sqlalchemy import create_engine, text, URL
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import declarative_base  # Cập nhật import để tránh cảnh báo
import logging
import json
import os
import base64

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = 'db_config.json'
MAPPING_FILE = 'mapping.json'

# Thiết lập cơ sở dữ liệu với SQLAlchemy
Base = declarative_base()

def get_db_session(engine):
    SessionLocal = scoped_session(sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    ))
    return SessionLocal

class LoginWindow:
    def __init__(self, master, on_success, on_close):
        self.master = master
        self.master.title("Đăng Nhập SQL Server")
        self.master.geometry("500x650")
        self.on_success = on_success
        self.on_close = on_close

        # Bind sự kiện đóng cửa sổ
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Frame chọn cấu hình đã lưu hoặc thêm mới
        frame_selection = tk.Frame(master)
        frame_selection.pack(pady=20)

        tk.Label(frame_selection, text="Chọn CSDL:", font=('Arial', 12)).pack(pady=5)
        self.connection_names = self.load_connection_names()
        self.selected_connection = tk.StringVar()
        self.combobox_connections = ttk.Combobox(frame_selection, values=self.connection_names + ["Thêm CSDL Mới"], state="readonly", width=40)
        self.combobox_connections.pack(pady=5)
        self.combobox_connections.bind("<<ComboboxSelected>>", self.on_combobox_select)

        # Frame nhập thông tin kết nối mới
        self.frame_new_connection = tk.Frame(master)
        # Ẩn frame mới kết nối ban đầu
        self.frame_new_connection.pack(pady=10)
        self.frame_new_connection.pack_forget()

        # Các trường nhập liệu cho kết nối mới
        tk.Label(self.frame_new_connection, text="Tên CSDL:", font=('Arial', 12)).pack(pady=5)
        self.name_entry = tk.Entry(self.frame_new_connection, width=50)
        self.name_entry.pack(pady=5)

        tk.Label(self.frame_new_connection, text="Server:", font=('Arial', 12)).pack(pady=5)
        self.server_entry = tk.Entry(self.frame_new_connection, width=50)
        self.server_entry.pack(pady=5)

        tk.Label(self.frame_new_connection, text="Database:", font=('Arial', 12)).pack(pady=5)
        self.database_entry = tk.Entry(self.frame_new_connection, width=50)
        self.database_entry.pack(pady=5)

        tk.Label(self.frame_new_connection, text="Username:", font=('Arial', 12)).pack(pady=5)
        self.username_entry = tk.Entry(self.frame_new_connection, width=50)
        self.username_entry.pack(pady=5)

        tk.Label(self.frame_new_connection, text="Password:", font=('Arial', 12)).pack(pady=5)
        self.password_entry = tk.Entry(self.frame_new_connection, width=50, show="*")
        self.password_entry.pack(pady=5)

        # Nút đăng nhập hoặc thêm mới
        self.btn_action = tk.Button(master, text="Đăng Nhập", command=self.attempt_login, width=20)
        self.btn_action.pack(pady=20)

    def on_closing(self):

        self.on_close()  # Gọi callback để đóng toàn bộ ứng dụng

    def load_connection_names(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                connections = config_data.get('connections', [])
                names = [conn['name'] for conn in connections]
                return names
            except Exception as e:
                logger.error(f"Lỗi khi tải cấu hình kết nối: {e}")
                return []
        return []

    def on_combobox_select(self, event):
        selected = self.combobox_connections.get()
        if selected == "Thêm CSDL Mới":
            self.frame_new_connection.pack(pady=10)
        else:
            self.frame_new_connection.pack_forget()

    def attempt_login(self):
        selected = self.combobox_connections.get()
        if selected == "Thêm CSDL Mới":
            # Lấy thông tin từ các Entry
            name = self.name_entry.get().strip()
            server = self.server_entry.get().strip()
            database = self.database_entry.get().strip()
            username = self.username_entry.get().strip()
            password = self.password_entry.get().strip()

            if not all([name, server, database, username, password]):
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập đầy đủ tất cả các trường.")
                return

            # Kiểm tra xem tên cấu hình đã tồn tại chưa
            if name in self.connection_names:
                messagebox.showwarning("Cảnh báo", f"Tên cấu hình '{name}' đã tồn tại. Vui lòng chọn tên khác.")
                return

            # Tạo connection URL bằng URL.create
            connection_url = URL.create(
                "mssql+pyodbc",
                username=username,
                password=password,
                host=server,
                port=1433,  # Bạn có thể tùy chỉnh nếu server của bạn sử dụng cổng khác
                database=database,
                query={
                    "driver": "ODBC Driver 18 for SQL Server",
                    "TrustServerCertificate": "yes",
                    "unicode_results": "yes"
                },
            )

            try:
                # Tạo engine
                engine = create_engine(
                    connection_url,
                    pool_pre_ping=True,
                    pool_recycle=1800,
                    pool_size=20,
                    echo=False  # Đặt thành True để bật logging SQL
                )
                # Kiểm tra kết nối
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

                # Mã hóa mật khẩu trước khi lưu
                encoded_password = base64.b64encode(password.encode('utf-8')).decode('utf-8')
                # Lưu cấu hình
                new_connection = {
                    'name': name,
                    'server': server,
                    'database': database,
                    'username': username,
                    'password': encoded_password
                }

                # Đọc cấu hình hiện tại
                config_data = {}
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                else:
                    config_data['connections'] = []

                # Thêm cấu hình mới
                config_data['connections'].append(new_connection)

                # Lưu lại vào tệp
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=4)
                logger.info(f"Đã thêm cấu hình kết nối '{name}' vào file.")

                # Gọi callback để mở giao diện chính
                self.master.destroy()
                self.on_success(engine)
            except Exception as e:
                logger.error(f"Lỗi khi kết nối đến SQL Server: {e}")
                messagebox.showerror("Lỗi", f"Lỗi khi kết nối đến SQL Server: {e}")
        else:
            # Sử dụng cấu hình đã lưu
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn một cấu hình kết nối hoặc thêm mới.")
                return

            try:
                # Đọc cấu hình
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                connections = config_data.get('connections', [])
                selected_conn = next((conn for conn in connections if conn['name'] == selected), None)

                if not selected_conn:
                    raise ValueError(f"Không tìm thấy cấu hình kết nối '{selected}'.")

                server = selected_conn['server']
                database = selected_conn['database']
                username = selected_conn['username']
                encoded_password = selected_conn['password']

                # Giải mã mật khẩu
                password = base64.b64decode(encoded_password.encode('utf-8')).decode('utf-8')

                # Tạo connection URL bằng URL.create
                connection_url = URL.create(
                    "mssql+pyodbc",
                    username=username,
                    password=password,
                    host=server,
                    port=1433,  # Bạn có thể tùy chỉnh nếu server của bạn sử dụng cổng khác
                    database=database,
                    query={
                        "driver": "ODBC Driver 18 for SQL Server",
                        "TrustServerCertificate": "yes",
                        "unicode_results": "yes"
                    },
                )

                # Tạo engine
                engine = create_engine(
                    connection_url,
                    pool_pre_ping=True,
                    pool_recycle=1800,
                    pool_size=20,
                    echo=False  # Đặt thành True để bật logging SQL
                )

                # Kiểm tra kết nối
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info(f"Kết nối đến SQL Server thành công với cấu hình '{selected}'.")

                # Gọi callback để mở giao diện chính
                self.master.destroy()
                self.on_success(engine)
            except Exception as e:
                logger.error(f"Lỗi khi kết nối đến SQL Server: {e}")
                messagebox.showerror("Lỗi", f"Lỗi khi kết nối đến SQL Server: {e}")

class ExcelToSQLApp:
    def __init__(self, root, engine):
        self.root = root
        self.root.title("Excel to SQL Server Mapper")
        self.root.geometry("1200x800")

        self.engine = engine
        self.SessionLocal = get_db_session(engine)

        # Biến lưu trữ DataFrame
        self.df = None

        # Lưu trữ các cột
        self.excel_columns = []
        self.sql_columns = []
        self.mapping = {}
        self.default_values = {}
        self.selected_table = None  # Biến để lưu bảng đã chọn

        # Tệp lưu mapping
        self.mapping_file = MAPPING_FILE

        # Bind sự kiện đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Tạo các phần của giao diện
        self.create_widgets()

        # Load mapping nếu đã tồn tại
        self.load_mapping()

    def create_widgets(self):
        # Frame đăng xuất
        frame_logout = tk.Frame(self.root)
        frame_logout.pack(fill="x", padx=10, pady=5)

        btn_logout = tk.Button(frame_logout, text="Đăng Xuất", command=self.logout, width=10)
        btn_logout.pack(side="right")

        # Frame chọn bảng
        frame_table = tk.Frame(self.root)
        frame_table.pack(pady=10)

        tk.Label(frame_table, text="Chọn Bảng SQL Server:", font=('Arial', 12)).pack(side="left", padx=5)

        self.combobox_tables = ttk.Combobox(frame_table, values=[], state="readonly", width=40)
        self.combobox_tables.pack(side="left", padx=5)
        self.combobox_tables.bind("<<ComboboxSelected>>", self.on_table_select)

        # Frame chọn file Excel
        frame_select = tk.Frame(self.root)
        frame_select.pack(pady=10)

        btn_select = tk.Button(frame_select, text="Chọn File Excel", command=self.select_excel, width=20)
        btn_select.pack()

        # Frame hiển thị dữ liệu mẫu từ Excel
        frame_sample = tk.LabelFrame(self.root, text="Dữ liệu mẫu từ Excel", padx=10, pady=10)
        frame_sample.pack(fill="both", expand=True, padx=10, pady=10)

        # Treeview để hiển thị dữ liệu mẫu
        self.tree_sample = ttk.Treeview(frame_sample, show='headings')
        self.tree_sample.pack(fill="both", expand=True, side="left")

        # Scrollbar cho Treeview dữ liệu mẫu
        scrollbar_sample = ttk.Scrollbar(frame_sample, orient="vertical", command=self.tree_sample.yview)
        self.tree_sample.configure(yscrollcommand=scrollbar_sample.set)
        scrollbar_sample.pack(side="right", fill="y")

        # Định nghĩa tag 'missing' để bôi màu các cell chứa null/Nan
        self.tree_sample.tag_configure('missing', foreground='red')  # Màu đỏ cho văn bản thiếu

        # Frame thao tác
        frame_actions = tk.Frame(self.root)
        frame_actions.pack(pady=10)

        btn_map = tk.Button(frame_actions, text="Map Cột", command=self.map_columns, width=15)
        btn_map.pack(side="left", padx=10)

        btn_insert = tk.Button(frame_actions, text="Ghi Dữ Liệu", command=self.insert_data, width=15)
        btn_insert.pack(side="left", padx=10)

        # Lấy danh sách bảng từ SQL Server
        self.get_sql_tables()

    def on_closing(self):
        try:
            # Đóng tất cả các session nếu có
            if hasattr(self, 'SessionLocal'):
                self.SessionLocal.remove()
                logger.info("Đã đóng tất cả các session SQLAlchemy.")
            # Đóng engine
            if hasattr(self, 'engine'):
                self.engine.dispose()
                logger.info("Đã đóng engine SQLAlchemy.")
        except Exception as e:
            logger.error(f"Lỗi khi đóng tài nguyên: {e}")
        self.root.destroy()

    def logout(self):
        confirm = messagebox.askyesno("Đăng Xuất", "Bạn có chắc chắn muốn đăng xuất?")
        if confirm:
            self.on_closing()
            main()

    def get_sql_tables(self):
        try:
            query = """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            """
            tables_df = pd.read_sql(query, con=self.engine)
            tables = tables_df['TABLE_NAME'].tolist()
            self.combobox_tables['values'] = tables
            if tables:
                self.combobox_tables.current(0)
                self.on_table_select(None)
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách bảng từ SQL Server: {e}")
            messagebox.showerror("Lỗi", f"Lỗi khi lấy danh sách bảng từ SQL Server: {e}")

    def on_table_select(self, event):
        selected = self.combobox_tables.get()
        if selected:
            self.selected_table = selected
            logger.info(f"Đã chọn bảng: {selected}")
            # Lấy danh sách các cột từ bảng đã chọn
            self.sql_columns = self.get_sql_columns(selected_table=selected)
            # Reset mapping và default_values
            self.mapping = {}
            self.default_values = {}
            # Nếu đã có mapping cho bảng này, load nó
            self.load_mapping()
            # Hiển thị dữ liệu mẫu nếu đã chọn file Excel
            if self.df is not None:
                self.display_sample_data()

    def select_excel(self):
        # Mở hộp thoại chọn file
        file_path = filedialog.askopenfilename(
            title="Chọn file Excel",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if file_path:
            try:
                # Đọc file Excel, sử dụng hàng thứ hai làm header
                self.df = pd.read_excel(file_path, header=1, dtype=str)  # Đọc tất cả cột dưới dạng string để hỗ trợ Unicode
                logger.info(f"Đã đọc file Excel: {file_path}")

                # Loại bỏ các cột không mong muốn bắt đầu bằng 'Unnamed'
                self.df = self.df.loc[:, ~self.df.columns.str.contains('^Unnamed')]
                logger.info("Đã loại bỏ các cột 'Unnamed'.")

                # Làm sạch tên các cột: loại bỏ khoảng trắng đầu và cuối, thay thế khoảng trắng giữa các từ bằng '_'
                self.df.columns = self.df.columns.str.strip().str.replace(' ', '_')
                logger.info("Đã làm sạch tên các cột trong DataFrame.")

                # Lấy danh sách các cột từ DataFrame
                self.excel_columns = self.df.columns.tolist()

                # Hiển thị dữ liệu mẫu
                self.display_sample_data()

            except Exception as e:
                logger.error(f"Lỗi khi đọc file Excel: {e}")
                messagebox.showerror("Lỗi", f"Lỗi khi đọc file Excel: {e}")

    def get_sql_columns(self, selected_table):
        try:
            query = f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{selected_table}'
            """
            columns_df = pd.read_sql(query, con=self.engine)
            columns = columns_df['COLUMN_NAME'].tolist()
            self.sql_columns_info = columns_df.set_index('COLUMN_NAME')[['DATA_TYPE', 'IS_NULLABLE']].to_dict(orient='index')
            logger.info(f"Các cột trong bảng '{selected_table}': {columns}")
            return columns
        except Exception as e:
            logger.error(f"Lỗi khi lấy cột từ SQL Server cho bảng '{selected_table}': {e}")
            messagebox.showerror("Lỗi", f"Lỗi khi lấy cột từ SQL Server cho bảng '{selected_table}': {e}")
            return []

    def display_sample_data(self):
        if self.df is not None:
            # Xóa các cột hiện tại trong tree_sample
            for col in self.tree_sample["columns"]:
                self.tree_sample.heading(col, text="")
                self.tree_sample.column(col, width=100)
            self.tree_sample["columns"] = list(self.df.columns)

            # Thiết lập tiêu đề cột
            for col in self.df.columns:
                self.tree_sample.heading(col, text=col)
                self.tree_sample.column(col, width=150)

            # Xóa các hàng hiện tại
            for row in self.tree_sample.get_children():
                self.tree_sample.delete(row)

            # Thêm tất cả dữ liệu vào Treeview
            for _, row in self.df.iterrows():
                # Kiểm tra và hiển thị các giá trị Unicode
                row_values = [str(value) if not pd.isna(value) else '' for value in row]

                # Kiểm tra xem dòng có chứa null/Nan không
                if any(pd.isna(value) for value in row):
                    self.tree_sample.insert('', 'end', values=row_values, tags=('missing',))
                else:
                    self.tree_sample.insert('', 'end', values=row_values)

    def map_columns(self):
        if not self.excel_columns:
            messagebox.showwarning("Cảnh báo", "Bạn cần phải chọn file Excel trước.")
            return

        if not self.selected_table:
            messagebox.showwarning("Cảnh báo", "Bạn cần phải chọn bảng SQL Server trước.")
            return

        # Tạo một cửa sổ mới để map cột
        mapping_window = tk.Toplevel(self.root)
        mapping_window.title(f"Map Cột Excel với SQL Server - Bảng '{self.selected_table}'")
        mapping_window.geometry("1000x700")  # Increased height to accommodate primary key selection

        # Bind sự kiện đóng cửa sổ mapping_window
        mapping_window.protocol("WM_DELETE_WINDOW", lambda: mapping_window.destroy())

        # Tạo một canvas và một scrollbar cho cửa sổ mapping
        canvas = tk.Canvas(mapping_window)
        scrollbar = ttk.Scrollbar(mapping_window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Tạo tiêu đề cho mapping
        lbl_excel = tk.Label(scrollable_frame, text="Cột Excel", font=('Arial', 12, 'bold'))
        lbl_excel.grid(row=0, column=0, padx=10, pady=10, sticky='w')

        lbl_sql = tk.Label(scrollable_frame, text="Cột SQL Server", font=('Arial', 12, 'bold'))
        lbl_sql.grid(row=0, column=1, padx=10, pady=10, sticky='w')

        lbl_sql_type = tk.Label(scrollable_frame, text="Kiểu Dữ Liệu SQL Server", font=('Arial', 12, 'bold'))
        lbl_sql_type.grid(row=0, column=2, padx=10, pady=10, sticky='w')

        lbl_default = tk.Label(scrollable_frame, text="Giá trị mặc định (nếu NULL)", font=('Arial', 12, 'bold'))
        lbl_default.grid(row=0, column=3, padx=10, pady=10, sticky='w')

        # Tạo các dòng để map cột
        self.mapping_widgets = {}  # Lưu trữ Combobox, Entry và Label cho từng cột Excel

        for idx, excel_col in enumerate(self.excel_columns, start=1):
            current_row = idx * 2 - 1  # Hàng lẻ cho widgets

            # Label cho cột Excel
            lbl = tk.Label(scrollable_frame, text=excel_col)
            lbl.grid(row=current_row, column=0, padx=10, pady=5, sticky='w')

            # Combobox cho cột SQL Server với tùy chọn "Not mapped"
            cmb = ttk.Combobox(scrollable_frame, values=self.sql_columns + ["Not mapped"], state="readonly", width=30)
            cmb.grid(row=current_row, column=1, padx=10, pady=5, sticky='w')

            # Nếu mapping đã tồn tại cho bảng này, tự động chọn
            existing_mapping = self.mapping.get(self.selected_table, {}).get('mapping', {})
            existing_default = self.mapping.get(self.selected_table, {}).get('default_values', {})
            if self.mapping and self.selected_table in self.mapping and excel_col in existing_mapping:
                cmb.set(existing_mapping[excel_col])
            else:
                cmb.set("Not mapped")  # Đặt giá trị mặc định là "Not mapped"

            # Label để hiển thị kiểu dữ liệu SQL Server
            lbl_type = tk.Label(scrollable_frame, text="", width=25, anchor='w')
            lbl_type.grid(row=current_row, column=2, padx=10, pady=5, sticky='w')

            # Entry để nhập giá trị mặc định
            ent = tk.Entry(scrollable_frame, width=30)
            ent.grid(row=current_row, column=3, padx=10, pady=5, sticky='w')

            # Nếu default value đã tồn tại, tự động điền
            if self.mapping and self.selected_table in self.mapping and self.mapping[self.selected_table]['mapping'].get(excel_col) in self.mapping[self.selected_table]['default_values']:
                ent.insert(0, str(self.mapping[self.selected_table]['default_values'][self.mapping[self.selected_table]['mapping'][excel_col]]))

            # Lưu các widgets vào mapping_widgets
            self.mapping_widgets[excel_col] = {'combobox': cmb, 'entry': ent, 'label_type': lbl_type}

            # Cập nhật kiểu dữ liệu nếu đã chọn
            if self.mapping and self.selected_table in self.mapping and excel_col in self.mapping[self.selected_table]['mapping']:
                selected_sql_col = self.mapping[self.selected_table]['mapping'][excel_col]
                sql_info = self.sql_columns_info.get(selected_sql_col, {})
                sql_type = sql_info.get('DATA_TYPE', "")
                lbl_type.config(text=sql_type)

            # Liên kết sự kiện thay đổi lựa chọn Combobox với hàm cập nhật kiểu dữ liệu
            cmb.bind("<<ComboboxSelected>>", lambda event, col=excel_col: self.update_sql_type(col))

            # Thêm đường kẻ ngang giữa các dòng
            if idx != len(self.excel_columns):
                separator = ttk.Separator(scrollable_frame, orient='horizontal')
                separator.grid(row=current_row + 1, column=0, columnspan=4, sticky='ew', padx=10, pady=5)

        # **NEW: Add Primary Key Selection**
        # Tạo nhãn cho chọn primary key
        lbl_primary = tk.Label(scrollable_frame, text="Chọn Cột So Sánh:", font=('Arial', 12, 'bold'))
        lbl_primary.grid(row=len(self.excel_columns) * 2, column=0, padx=10, pady=10, sticky='w')

        # Tạo Combobox để chọn primary key từ các cột SQL Server đã được map
        self.primary_key_var = tk.StringVar()
        self.combobox_primary_key = ttk.Combobox(scrollable_frame, values=self.sql_columns, state="readonly", width=30, textvariable=self.primary_key_var)
        self.combobox_primary_key.grid(row=len(self.excel_columns) * 2, column=1, padx=10, pady=10, sticky='w')

        # Nếu đã có primary key trong mapping, tự động chọn
        existing_primary_key = self.mapping.get(self.selected_table, {}).get('primary_key', "")
        if existing_primary_key:
            self.combobox_primary_key.set(existing_primary_key)

        # **END NEW**

        # Button lưu mapping và đóng cửa sổ
        btn_save = tk.Button(scrollable_frame, text="Lưu Mapping", command=lambda: self.save_mapping(mapping_window), width=20)
        btn_save.grid(row=len(self.excel_columns) * 2 + 1, column=0, columnspan=4, pady=20)

    def update_sql_type(self, excel_col):
        """
        Cập nhật kiểu dữ liệu SQL Server cho cột Excel tương ứng.
        """
        selected_sql_col = self.mapping_widgets[excel_col]['combobox'].get()
        if selected_sql_col != "Not mapped":
            sql_info = self.sql_columns_info.get(selected_sql_col, {})
            sql_type = sql_info.get('DATA_TYPE', "")
        else:
            sql_type = ""
        self.mapping_widgets[excel_col]['label_type'].config(text=sql_type)

    def save_mapping(self, mapping_window):
        if not self.selected_table:
            messagebox.showwarning("Cảnh báo", "Bạn cần phải chọn bảng SQL Server trước.")
            return

        mapping = {}
        default_values = {}
        mapped_sql_columns = set()

        for excel_col, widgets in self.mapping_widgets.items():
            sql_col = widgets['combobox'].get()
            default_val = widgets['entry'].get()
            if sql_col and sql_col != "Not mapped":
                mapping[excel_col] = sql_col
                mapped_sql_columns.add(sql_col)
                if default_val:
                    # Kiểm tra và chuyển đổi giá trị mặc định dựa trên kiểu dữ liệu của cột SQL Server
                    data_type = self.sql_columns_info.get(sql_col, {}).get('DATA_TYPE', "").lower()
                    try:
                        if data_type in ['int', 'bigint', 'smallint', 'tinyint']:
                            converted_val = int(default_val)
                        elif data_type in ['float', 'real', 'decimal', 'numeric']:
                            converted_val = float(default_val)
                        else:
                            converted_val = default_val  # Dữ liệu kiểu chuỗi
                        default_values[sql_col] = converted_val
                    except ValueError:
                        messagebox.showerror("Lỗi", f"Giá trị mặc định cho cột '{sql_col}' không hợp lệ với kiểu dữ liệu '{data_type}'.")
                        return

        if not mapping:
            messagebox.showwarning("Cảnh báo", "Bạn chưa map bất kỳ cột nào.")
            return

        # **NEW: Validate Primary Key Selection**
        primary_key = self.primary_key_var.get()
        if not primary_key:
            messagebox.showwarning("Cảnh báo", "Bạn cần phải chọn một cột làm mốc so sánh (Primary Key).")
            return

        if primary_key not in mapped_sql_columns:
            messagebox.showerror("Lỗi", "Cột được chọn làm Primary Key phải là một trong các cột đã được map.")
            return
        # **END NEW**

        # Lưu mapping và default_values vào cấu trúc dữ liệu với table name
        if self.selected_table not in self.mapping:
            self.mapping[self.selected_table] = {}

        self.mapping[self.selected_table]['mapping'] = mapping
        self.mapping[self.selected_table]['default_values'] = default_values

        # **NEW: Save Primary Key**
        self.mapping[self.selected_table]['primary_key'] = primary_key
        # **END NEW**

        # Xác định các cột SQL Server không được map
        unmapped_sql_columns = set(self.sql_columns) - mapped_sql_columns

        if unmapped_sql_columns:
            # Mở cửa sổ mới để nhập giá trị mặc định cho các cột SQL Server không được map
            self.input_default_values(unmapped_sql_columns, mapping_window)
        else:
            # Save mapping to JSON file
            try:
                with open(self.mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(self.mapping, f, ensure_ascii=False, indent=4)
                logger.info("Đã lưu mapping vào file.")
            except Exception as e:
                logger.error(f"Lỗi khi lưu mapping: {e}")
                messagebox.showerror("Lỗi", f"Lỗi khi lưu mapping: {e}")
                return

            messagebox.showinfo("Thành công", "Đã lưu mapping thành công.")
            mapping_window.destroy()

    def input_default_values(self, unmapped_sql_columns, mapping_window):
        default_window = tk.Toplevel(mapping_window)
        default_window.title("Giá trị mặc định cho các cột SQL Server không được map")
        default_window.geometry("500x400")

        # Bind sự kiện đóng cửa sổ default_window
        default_window.protocol("WM_DELETE_WINDOW", lambda: default_window.destroy())

        # Tạo một canvas và một scrollbar cho cửa sổ default
        canvas = tk.Canvas(default_window)
        scrollbar = ttk.Scrollbar(default_window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Lưu các Entry để lấy giá trị mặc định
        self.default_entries = {}

        for idx, sql_col in enumerate(unmapped_sql_columns, start=1):
            lbl = tk.Label(scrollable_frame, text=sql_col, font=('Arial', 10, 'bold'))
            lbl.grid(row=idx, column=0, padx=10, pady=5, sticky='w')

            ent = tk.Entry(scrollable_frame, width=30)
            ent.grid(row=idx, column=1, padx=10, pady=5, sticky='w')

            self.default_entries[sql_col] = ent

        # Button để lưu giá trị mặc định và đóng cửa sổ
        def save_defaults():
            for sql_col, ent in self.default_entries.items():
                value = ent.get().strip()
                if value == '':
                    messagebox.showwarning("Cảnh báo", f"Vui lòng nhập giá trị mặc định cho cột '{sql_col}'.")
                    return
                # Kiểm tra và chuyển đổi giá trị mặc định dựa trên kiểu dữ liệu của cột SQL Server
                data_type = self.sql_columns_info.get(sql_col, {}).get('DATA_TYPE', "").lower()
                try:
                    if data_type in ['int', 'bigint', 'smallint', 'tinyint']:
                        converted_value = int(value)
                    elif data_type in ['float', 'real', 'decimal', 'numeric']:
                        converted_value = float(value)
                    else:
                        converted_value = value  # Dữ liệu kiểu chuỗi
                    self.mapping[self.selected_table]['default_values'][sql_col] = converted_value
                except ValueError:
                    messagebox.showerror("Lỗi", f"Giá trị mặc định cho cột '{sql_col}' không hợp lệ với kiểu dữ liệu '{data_type}'.")
                    return

            # Save mapping and default_values to JSON
            try:
                with open(self.mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(self.mapping, f, ensure_ascii=False, indent=4)
                logger.info("Đã lưu mapping và giá trị mặc định vào file.")
            except Exception as e:
                logger.error(f"Lỗi khi lưu mapping và giá trị mặc định: {e}")
                messagebox.showerror("Lỗi", f"Lỗi khi lưu mapping và giá trị mặc định: {e}")
                return

            messagebox.showinfo("Thành công", "Đã lưu mapping và giá trị mặc định thành công.")
            default_window.destroy()
            mapping_window.destroy()

        btn_save = tk.Button(scrollable_frame, text="Lưu Defaults và Đóng", command=save_defaults, width=20)
        btn_save.grid(row=len(unmapped_sql_columns)+1, column=0, columnspan=2, pady=20)

    def insert_data(self):
        if not self.mapping or self.selected_table not in self.mapping:
            messagebox.showwarning("Cảnh báo", "Bạn cần phải map các cột trước khi ghi dữ liệu.")
            return
        try:
            # Tạo một bản sao của DataFrame để tránh thay đổi trực tiếp
            df_mapped = self.df.copy()

            # Đổi tên các cột theo mapping
            df_mapped = df_mapped.rename(columns=self.mapping[self.selected_table]['mapping'])

            # Lấy danh sách các cột đã map
            mapped_sql_columns = list(self.mapping[self.selected_table]['mapping'].values())

            # Xác định các cột SQL Server không được map
            unmapped_sql_columns = set(self.sql_columns) - set(mapped_sql_columns)

            # Thêm giá trị mặc định cho các cột SQL Server không được map
            for sql_col in unmapped_sql_columns:
                if sql_col in self.mapping[self.selected_table]['default_values']:
                    df_mapped[sql_col] = self.mapping[self.selected_table]['default_values'][sql_col]
                else:
                    # Kiểm tra xem cột có cho phép NULL không
                    is_nullable = self.sql_columns_info.get(sql_col, {}).get('IS_NULLABLE', 'NO')
                    if is_nullable == 'YES':
                        self.df[sql_col] = None
                    else:
                        messagebox.showerror("Lỗi", f"Không thể đặt giá trị NULL cho cột '{sql_col}' vì cột này không cho phép NULL và không có giá trị mặc định.")
                        logger.error(f"Cột '{sql_col}' không cho phép NULL và không có giá trị mặc định.")
                        return

            # **Áp dụng giá trị mặc định cho các cột đã được map nếu chúng chứa NaN**
            for sql_col in mapped_sql_columns:
                if sql_col in self.mapping[self.selected_table]['default_values']:
                    df_mapped[sql_col] = df_mapped[sql_col].fillna(self.mapping[self.selected_table]['default_values'][sql_col])

            # Lấy danh sách các cột cần ghi vào SQL Server
            sql_columns = list(mapped_sql_columns) + list(unmapped_sql_columns)

            # Chỉ giữ lại các cột đã map và các cột không được map với giá trị mặc định
            df_mapped = df_mapped[sql_columns]

            # Chuyển đổi các cột DataFrame sang kiểu dữ liệu phù hợp
            for col in sql_columns:
                data_type = self.sql_columns_info.get(col, {}).get('DATA_TYPE', "").lower()
                if data_type in ['int', 'bigint', 'smallint', 'tinyint']:
                    df_mapped[col] = pd.to_numeric(df_mapped[col], errors='coerce').astype('Int64')  # Sử dụng kiểu Int64 để hỗ trợ NA
                elif data_type in ['float', 'real', 'decimal', 'numeric']:
                    df_mapped[col] = pd.to_numeric(df_mapped[col], errors='coerce')
                else:
                    df_mapped[col] = df_mapped[col].astype(str).replace('nan', None)

            # **Kiểm Tra Dữ Liệu Sau Khi Chuyển Đổi**
            logger.debug(f"Dữ liệu sau khi chuyển đổi:\n{df_mapped.head()}")

            # **NEW: Retrieve the selected primary key**
            primary_key_column = self.mapping[self.selected_table].get('primary_key')
            if not primary_key_column:
                messagebox.showerror("Lỗi", "Không tìm thấy cột Primary Key cho bảng này.")
                logger.error("Primary Key chưa được thiết lập.")
                return
            # **END NEW**

            logger.info(f"Primary Key Column: {primary_key_column}")

            # Thực hiện upsert từng dòng
            errors = []  # Danh sách để lưu trữ các lỗi
            with self.engine.begin() as conn:  # Sử dụng begin() để tự động commit giao dịch
                for index, row in df_mapped.iterrows():
                    # Lấy giá trị của cột primary key
                    primary_key_value = row.get(primary_key_column)
                    if primary_key_value is None:
                        logger.warning(f"Dòng {index} không có '{primary_key_column}', bỏ qua.")
                        continue

                    # Kiểm tra và chuyển đổi primary_key_value theo kiểu dữ liệu
                    data_type = self.sql_columns_info.get(primary_key_column, {}).get('DATA_TYPE', "").lower()
                    try:
                        if data_type in ['int', 'bigint', 'smallint', 'tinyint']:
                            primary_key_value = int(primary_key_value)
                        elif data_type in ['float', 'real', 'decimal', 'numeric']:
                            primary_key_value = float(primary_key_value)
                        else:
                            primary_key_value = str(primary_key_value)
                    except ValueError:
                        error_msg = f"Dòng {index}: '{primary_key_column}' không hợp lệ - {primary_key_value}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue

                    logger.debug(f"Processing {primary_key_column}: {primary_key_value}")

                    # Kiểm tra xem primary_key_value đã tồn tại chưa
                    select_query = text(f"SELECT COUNT(*) FROM {self.selected_table} WHERE {primary_key_column} = :pk")
                    try:
                        result = conn.execute(select_query, {"pk": primary_key_value})
                        count = result.scalar()
                        result.close()
                    except Exception as e:
                        error_msg = f"Dòng {index}: Lỗi khi thực thi truy vấn SELECT - {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue

                    if count > 0:
                        # Thực hiện cập nhật
                        update_columns = [f"{col} = :{col}" for col in sql_columns if col != primary_key_column]
                        update_query = text(f"UPDATE {self.selected_table} SET {', '.join(update_columns)} WHERE {primary_key_column} = :pk")
                        params = {col: row[col] for col in sql_columns if col != primary_key_column}
                        params['pk'] = primary_key_value
                        try:
                            conn.execute(update_query, params)
                            logger.debug(f"Cập nhật {primary_key_column} {primary_key_value}")
                        except Exception as e:
                            error_msg = f"Dòng {index}: Lỗi khi cập nhật - {e}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            continue
                    else:
                        # Thực hiện chèn mới
                        insert_query = text(f"INSERT INTO {self.selected_table} ({', '.join(sql_columns)}) VALUES ({', '.join([':'+col for col in sql_columns])})")
                        params = {col: row[col] for col in sql_columns}
                        try:
                            conn.execute(insert_query, params)
                            logger.debug(f"Chèn {primary_key_column} {primary_key_value}")
                        except Exception as e:
                            error_msg = f"Dòng {index}: Lỗi khi chèn - {e}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            continue

            if errors:
                # Nếu có lỗi, hiển thị tất cả lỗi trong một hộp thoại
                error_text = "\n".join(errors)
                messagebox.showerror("Lỗi trong quá trình ghi dữ liệu", f"Dữ liệu ở các dòng sau không được ghi:\n{error_text}")
            else:
                # Nếu không có lỗi, thông báo thành công
                logger.info(f"Đã ghi dữ liệu vào bảng '{self.selected_table}' thành công.")
                messagebox.showinfo("Thành công", f"Đã ghi dữ liệu vào bảng '{self.selected_table}' thành công.")

            # Cập nhật dữ liệu mẫu sau khi ghi
            self.display_sample_data()
        except Exception as e:
            logger.error(f"Lỗi khi ghi dữ liệu: {e}")
            messagebox.showerror("Lỗi", f"Lỗi khi ghi dữ liệu: {e}")

    def load_mapping(self):
        if os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, 'r', encoding='utf-8') as f:
                    self.mapping = json.load(f)
                logger.info("Đã tải mapping từ file.")
            except Exception as e:
                logger.error(f"Lỗi khi tải mapping: {e}")
                messagebox.showerror("Lỗi", f"Lỗi khi tải mapping: {e}")

    def save_mapping_file(self):
        try:
            with open(self.mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self.mapping, f, ensure_ascii=False, indent=4)
            logger.info("Đã lưu mapping vào file.")
        except Exception as e:
            logger.error(f"Lỗi khi lưu mapping: {e}")
            messagebox.showerror("Lỗi", f"Lỗi khi lưu mapping: {e}")

def main():
    root = tk.Tk()
    root.withdraw()  # Ẩn cửa sổ chính trước khi đăng nhập

    def on_login_success(engine):
        root.deiconify()  # Hiển thị cửa sổ chính sau khi đăng nhập thành công
        app = ExcelToSQLApp(root, engine)

    def on_login_close():
        root.destroy()  # Đóng toàn bộ ứng dụng khi cửa sổ đăng nhập bị đóng

    # Kiểm tra xem đã có cấu hình kết nối chưa
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            connections = config_data.get('connections', [])

            if not connections:
                raise ValueError("Không tìm thấy bất kỳ cấu hình kết nối nào.")

            # Nếu có cấu hình, mở cửa sổ đăng nhập để chọn hoặc thêm mới
            login_window = tk.Toplevel(root)
            login_app = LoginWindow(login_window, on_login_success, on_login_close)
            root.mainloop()
        except Exception as e:
            logger.error(f"Lỗi khi tải cấu hình kết nối: {e}")
            messagebox.showerror("Lỗi", f"Lỗi khi tải cấu hình kết nối: {e}")
            # Mở cửa sổ đăng nhập mới
            login_window = tk.Toplevel(root)
            login_app = LoginWindow(login_window, on_login_success, on_login_close)
            root.mainloop()
    else:
        # Nếu không có cấu hình, mở cửa sổ đăng nhập
        login_window = tk.Toplevel(root)
        login_app = LoginWindow(login_window, on_login_success, on_login_close)
        root.mainloop()

if __name__ == "__main__":
    main()
