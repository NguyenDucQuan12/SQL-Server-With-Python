import queue
import threading
import time
import pyodbc
from datetime import datetime

pyodbc.pooling = True  
data_queue = queue.Queue()

def db_writer_thread_func(connection_string, thread_id):
    while True:
        try:
            record = data_queue.get()
            if record is None:
                print(f"[Writer {thread_id}] Nhận tín hiệu dừng. Kết thúc thread.")
                break

            # Lấy thời gian hiện tại (có thể lưu dạng datetime hoặc string)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Mở kết nối (được Pool hỗ trợ) chỉ khi cần ghi
            with pyodbc.connect(connection_string) as conn:
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO TestTable 
                            (Column1, Column2, Column3, Column4, Time)
                        VALUES (?, ?, ?, ?, ?)
                    """
                    cursor.execute(sql, (
                        record['col1'], 
                        record['col2'], 
                        record['col3'], 
                        record['col4'],
                        now_str  # cột thời gian
                    ))
                    conn.commit()

        except Exception as e:
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

def sensor_thread_func(sensor_id, times):
    """
    times: list các thời điểm hoặc khoảng thời gian giả lập cảm biến gửi dữ liệu.
    Mỗi times[i] ta gửi data_queue.put(...) -> mô phỏng giai đoạn 'dồn dập'
    """
    for t in times:
        time.sleep(t['delay'])
        for i in range(t['count']):
            data_queue.put({
                'col1': f"Sensor{sensor_id}",
                'col2': f"Data{i}",
                'col3': i,
                'col4': "Xin chào CSDL Test"
            })
            time.sleep(0.1)  # Tần suất ghi

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

    # Giả lập 2 khoảng thời gian sensor gửi dữ liệu
    times_sensor1 = [
        {'delay': 5, 'count': 5},
        {'delay': 20, 'count': 10},
    ]

    # Tạo 3 thread sensor
    sensor_threads = []
    for sid in range(3):
        t = threading.Thread(target=sensor_thread_func, args=(sid, times_sensor1))
        t.start()
        sensor_threads.append(t)

    # Chờ tất cả sensor xong
    for t in sensor_threads:
        t.join()

    # Gửi tín hiệu dừng cho 2 writer threads
    data_queue.put(None)
    data_queue.put(None)

    writer_thread_1.join()
    writer_thread_2.join()

    print("Hoàn tất gửi dữ liệu và ghi vào SQL Server")

if __name__ == "__main__":
    main()
