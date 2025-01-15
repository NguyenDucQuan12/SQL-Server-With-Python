# SQL-Server-With-Python

## 1. Cài đặt SQL Server và SQL Server Manager Studio
Tải SQL Server từ trang chủ Microsoft [tại đây](https://www.microsoft.com/en-us/sql-server/sql-server-downloads). Mình đang dùng với phiên bản `Express`. Tải về và cài đặt theo mục `Basic`.  

![alt text](Image/download_sqlserver.png)

Sau khi cài xong `SQL Server` thì tiếp tục tải và cài đạt `SQL Server Management Studio (SSMS)`.  

![alt text](Image/download_ssms.png)

Sau đó mở `SSMS` lên và kích hoạt một số chức năng bằng cách sau:  
Bước 1 mở `Server Properties` bằng cách click chuột phải vào tên server và chọn `Properties`  

![alt text](Image/open_server_properties.png)

Bước 2 cho phép đăng nhập SQL Server bằng tài khoản:  

![alt text](Image/active_SQL_login.png)

Bước 3: Kích hoạt tài khoản `sa` để đăng nhập.  

![alt text](Image/open_properties_sa_account.png)

Sau đó chọn `Properties` để cấu hình tài khoản.  
Bước 4: Kích hoạt tài khoản sa và đặt mật khẩu  

![alt text](Image/enable_sa_account.png)

![alt text](Image/set_password_sa_account.png)

Khởi động lại SQL Server là đã hoàn tất cài đặt SQL Server

## 2. Cấu hình SQL Server bằng SQL Server Configuration Manager

