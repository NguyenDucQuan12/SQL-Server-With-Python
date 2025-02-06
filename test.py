import pyodbc
import re

def get_odbc_drivers_for_sql_server():
    # Lấy danh sách tất cả các ODBC drivers cài đặt trên hệ thống
    drivers = pyodbc.drivers()

    # Biểu thức chính quy để tìm các driver có dạng "ODBC Driver xx for SQL Server"
    pattern = re.compile(r"ODBC Driver \d+ for SQL Server")
    
    # Lọc các driver có tên phù hợp với biểu thức chính quy
    odbc_drivers = [driver for driver in drivers if pattern.match(driver)]
    
    return odbc_drivers

# Lấy danh sách các ODBC drivers cho SQL Server
odbc_drivers = get_odbc_drivers_for_sql_server()

if odbc_drivers:
    print("Các ODBC Driver cho SQL Server được tìm thấy:")
    for driver in odbc_drivers:
        print(driver)
else:
    print("Không tìm thấy ODBC Driver cho SQL Server nào.")
