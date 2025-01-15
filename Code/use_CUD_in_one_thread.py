import queue
import threading
import time
import pyodbc
from datetime import datetime

pyodbc.pooling = True
data_queue = queue.Queue()

def db_writer_thread_func(connection_string, thread_id):
    """
    Thread này lấy từng 'record' từ data_queue.
    Tùy action (insert/update/delete) để thực hiện truy vấn.
    """
    while True:
        try:
            record = data_queue.get()
            if record is None:
                print(f"[Writer {thread_id}] Nhận tín hiệu dừng. Kết thúc thread.")
                break

            action = record.get('action')
            
            # Mở kết nối (tận dụng Pooling)
            with pyodbc.connect(connection_string) as conn:
                # Nếu muốn gộp nhiều lệnh, ta có thể tắt autocommit, 
                # còn ở đây ta autocommit từng lệnh cho đơn giản.
                # conn.autocommit = False
                with conn.cursor() as cursor:
                    # Tuỳ action mà chạy SQL khác nhau
                    if action == 'insert':
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        sql = """
                            INSERT INTO TestTable (Column1, Column2, Column3, Column4, Time)
                            VALUES (?, ?, ?, ?, ?)
                        """
                        cursor.execute(sql, (
                            record['col1'],
                            record['col2'],
                            record['col3'],
                            record['col4'],
                            now_str
                        ))
                        # conn.commit()  # nếu tắt autocommit thì cần commit thủ công
                        
                    elif action == 'update':
                        sql = """
                            UPDATE TestTable
                            SET Column2 = ?, Column3 = ?
                            WHERE ID = ?
                        """
                        cursor.execute(sql, (
                            record['new_col2'],
                            record['new_col3'],
                            record['id']
                        ))
                        # conn.commit()
                        
                    elif action == 'delete':
                        sql = "DELETE FROM TestTable WHERE ID = ?"
                        cursor.execute(sql, (record['id'],))
                        # conn.commit()
                        
                    else:
                        print(f"[Writer {thread_id}] Action không hợp lệ: {action}")

        except Exception as e:
            # Trong tình huống tắt autocommit, bạn mới cần rollback() rõ ràng
            # conn.rollback()  # nếu ta sử dụng transaction thủ công
            print(f"[Writer {thread_id}] Lỗi khi ghi dữ liệu: {e}")
        finally:
            data_queue.task_done()

def start_db_writer(connection_string, thread_id):
    writer_thread = threading.Thread(
        target=db_writer_thread_func,
        args=(connection_string, thread_id,),
        daemon=True
    )
    writer_thread.start()
    return writer_thread

def sensor_thread_func(sensor_id):
    """
    Mô phỏng "sensor" (hoặc bất kỳ logic nào) gửi các thao tác CUD vào queue.
    Ở đây, ta ví dụ: 3 insert, 1 update, 1 delete.
    """
    # 1) INSERT 3 bản ghi
    for i in range(3):
        data_queue.put({
            'action': 'insert',
            'col1': f"Sensor{sensor_id}",
            'col2': f"Data{i}",
            'col3': i,
            'col4': "Xin chào CSDL"
        })
        time.sleep(0.2)

    # 2) Update 1 bản ghi (giả sử ta muốn update record ID=2 chẳng hạn)
    # Thực tế ID=2 phải tồn tại sẵn, 
    # hoặc tuỳ logic bạn có thể SELECT ID rồi put vào queue.
    data_queue.put({
        'action': 'update',
        'id': 2,
        'new_col2': f"Updated by Sensor {sensor_id}",
        'new_col3': 999
    })

    time.sleep(0.2)

    # 3) Delete 1 bản ghi (thử xóa ID=3)
    data_queue.put({
        'action': 'delete',
        'id': 3
    })

def do_select_data(connection_string):
    """
    Hàm SELECT, đọc dữ liệu trực tiếp (main thread).
    """
    with pyodbc.connect(connection_string) as conn:
        with conn.cursor() as cursor:
            rows = cursor.execute("""
                SELECT ID, Column1, Column2, Column3, Column4, [Time] 
                FROM TestTable
                ORDER BY ID
            """).fetchall()
            
            print("\n--- Kết quả SELECT từ TestTable ---")
            for row in rows:
                # row là tuple (ID, Column1, Column2, Column3, Column4, Time)
                print(row)
            print("------------------------------------\n")

def main():
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=TestDB;"
        "UID=sa;"
        "PWD=123456789;"
        "TrustServerCertificate=yes;"
    )

    # Tạo 2 thread writer
    writer_thread_1 = start_db_writer(connection_string, thread_id=1)
    writer_thread_2 = start_db_writer(connection_string, thread_id=2)

    # Tạo 3 sensor threads
    sensor_threads = []
    for sid in range(3):
        t = threading.Thread(target=sensor_thread_func, args=(sid,))
        t.start()
        sensor_threads.append(t)

    # Chờ tất cả sensor xong
    for t in sensor_threads:
        t.join()

    # Gửi tín hiệu dừng cho 2 writer threads (mỗi thread cần 1 None)
    data_queue.put(None)
    data_queue.put(None)

    # Chờ hai writer dừng hẳn
    writer_thread_1.join()
    writer_thread_2.join()

    # Bây giờ ta thực hiện SELECT ở main
    do_select_data(connection_string)

    print("Hoàn tất CUD + SELECT dữ liệu trong SQL Server")

if __name__ == "__main__":
    main()
