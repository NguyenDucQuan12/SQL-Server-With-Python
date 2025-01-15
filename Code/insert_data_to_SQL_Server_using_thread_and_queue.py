import queue
import threading
import time
import pyodbc

# ===== KÍCH HOẠT CONNECTION POOLING CHO pyodbc =====
# Mặc định pyodbc.pooling = True, nhưng vẫn đặt lại cho chắc ăn
pyodbc.pooling = True  

# Hàng đợi lưu các bản ghi cần ghi xuống database
data_queue = queue.Queue()

# Hàm ghi dữ liệu xuống SQL Server (dùng 1 Thread duy nhất)
def db_writer_thread_func(connection_string):
    """Thread này chạy liên tục, lấy dữ liệu từ Queue và ghi xuống DB."""
    
    while True:
        try:
            # Lấy dữ liệu từ Queue, nếu rỗng thì block đến khi có dữ liệu
            record = data_queue.get()
            # Nếu không còn bản ghi nào để ghi vào CSDL thì dừng luồng này
            if record is None:
                break

            # ========== MỞ KẾT NỐI CHO MỖI LẦN GHI ==========
            # Nhờ Connection Pooling, thao tác này sẽ được tái sử dụng kết nối
            with pyodbc.connect(connection_string) as conn:
                with conn.cursor() as cursor:
                    # Ví dụ: Ghi record vào bảng TestTable (có cột Column1..4)
                    sql = """
                        INSERT INTO TestTable(Column1, Column2, Column3, Column4)
                        VALUES (?, ?, ?, ?)
                    """
                    cursor.execute(sql, (
                        record['col1'],
                        record['col2'],
                        record['col3'],
                        record['col4']
                    ))
                    conn.commit()  # Xác nhận ghi dữ liệu

        except Exception as e:
            print(f"Lỗi khi ghi dữ liệu: {e}")
        finally:
            # Đánh dấu đã xử lý xong item trong Queue
            data_queue.task_done()

def start_db_writer(connection_string):
    """Hàm này tạo và khởi động thread chuyên ghi dữ liệu."""
    writer_thread = threading.Thread(
        target=db_writer_thread_func, 
        args=(connection_string,),
        daemon=True
    )
    writer_thread.start()
    return writer_thread

# ==========================
# Main xử lý các luồng khác
# ==========================
def main():
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=TestDB;"
        "UID=sa;"
        "PWD=123456789;"
        "TrustServerCertificate=yes"
    )
    
    # Khởi động thread chuyên ghi dữ liệu
    writer_thread = start_db_writer(connection_string)
    
    # Giả sử có 3 luồng sensor sinh ra dữ liệu
    def sensor_thread_func(sensor_id):
        for i in range(5):
            data = {
                'col1': f"Sensor{sensor_id}",
                'col2': f" Hello {i}",
                'col3': i,
                'col4': "No name in SQL"
            }
            # Đẩy dữ liệu vào hàng đợi
            data_queue.put(data)
            time.sleep(0.5)  # Giả lập độ trễ

    # Tạo và chạy các luồng sensor
    sensor_threads = []
    for sid in range(3):
        t = threading.Thread(target=sensor_thread_func, args=(sid,))
        t.start()
        sensor_threads.append(t)
    
    # Chờ các luồng sensor kết thúc
    for t in sensor_threads:
        t.join()

    # Sau khi xong, gửi tín hiệu dừng cho thread ghi
    data_queue.put(None)
    writer_thread.join()

if __name__ == "__main__":
    main()
