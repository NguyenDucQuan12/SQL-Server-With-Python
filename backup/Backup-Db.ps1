param(
  [Parameter(Mandatory=$true)] [string]$Instance  = ".\SQLEXPRESS",
  [Parameter(Mandatory=$true)] [string]$Database  = "Docker_DB",
  [Parameter(Mandatory=$true)] [string]$BasePath  = "E:\SQL_Backup",
  [Parameter(Mandatory=$true)] [ValidateSet("Full","Diff","Log")] [string]$Type,
  [Parameter(Mandatory=$true)] [int]$Stripes      = 1
)

# 1) Tạo thư mục: E:\SQL_Backup\<DB>\<Type>\<YYYYMMDD>\
$day = Get-Date -Format "yyyyMMdd"
$dir = Join-Path $BasePath (Join-Path $Database (Join-Path $Type $day))
New-Item -ItemType Directory -Force -Path $dir | Out-Null

# 2) Tạo danh sách file striping
$time   = Get-Date -Format "HHmmss"
$ext    = if ($Type -eq "Log") { "trn" } elseif ($Type -eq "Diff") { "dif" } else { "bak" }
$targets = @()
for ($i=1; $i -le $Stripes; $i++) {
  $targets += (Join-Path $dir ("{0}_{1}_{2}_{3}.{4}" -f $Database, $Type.ToUpper(), $time, $i, $ext))
}
# DISK = N'path' , DISK = N'path2'
$disks = ($targets | ForEach-Object { "DISK = N'" + $_.Replace("'", "''") + "'" }) -join ", "

# 3) Sinh T-SQL rõ ràng (không “xâu chuỗi phức tạp”)
if ($Type -eq "Full") {
  $tsql = @"
IF SERVERPROPERTY('EngineEdition') <> 4
BEGIN
  BACKUP DATABASE [$Database]
  TO $disks
  WITH COMPRESSION, CHECKSUM, STATS = 5;
END
ELSE
BEGIN
  BACKUP DATABASE [$Database]
  TO $disks
  WITH CHECKSUM, STATS = 5;
END;
RESTORE VERIFYONLY FROM $disks WITH CHECKSUM;
"@
}
elseif ($Type -eq "Diff") {
  $tsql = @"
BACKUP DATABASE [$Database]
TO $disks
WITH DIFFERENTIAL, CHECKSUM, STATS = 5;
"@
}
else { # Log
  $tsql = @"
IF EXISTS (
  SELECT 1
  FROM sys.dm_exec_requests
  WHERE command IN ('BACKUP DATABASE','BACKUP LOG')
    AND database_id = DB_ID(N'$Database')
)
BEGIN
  PRINT 'Backup in progress. Skipping LOG backup.';
  RETURN;
END;

BACKUP LOG [$Database]
TO $disks
WITH CHECKSUM, STATS = 5;
"@
}

# (Tùy chọn) In ra để bạn xem thử trước khi chạy
# Write-Host "===== T-SQL to run ====="
# Write-Host $tsql

# 4) Thực thi qua sqlcmd
# -NoProfile & -ExecutionPolicy Bypass nên dùng khi gọi từ Task Scheduler, ở đây không cần.
& sqlcmd -S $Instance -d master -E -b -Q $tsql
if ($LASTEXITCODE -ne 0) { throw "Backup failed with exit code $LASTEXITCODE" }

Write-Host "Backup $Type completed. Files:"
$targets | ForEach-Object { Write-Host "  $_" }
