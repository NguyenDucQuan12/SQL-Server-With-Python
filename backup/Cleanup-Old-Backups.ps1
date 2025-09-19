param(
  [Parameter(Mandatory=$true)]  [string]$BasePath = "E:\SQL_Backup",
  [Parameter(Mandatory=$false)] [string]$Database,                  # nếu bỏ trống: xử lý tất cả DB trong $BasePath
  [Parameter(Mandatory=$false)] [int]$FullDays = 21,
  [Parameter(Mandatory=$false)] [int]$DiffDays = 14,
  [Parameter(Mandatory=$false)] [int]$LogDays  = 7,
  [Parameter(Mandatory=$false)] [string]$LogFile = "C:\Scripts\cleanup-backups.log",
  [switch]$WhatIf                                                  # dry-run (không xóa thực sự)
)

# --- tiện ích log ---
function Write-Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    if ($LogFile) { Add-Content -Path $LogFile -Value $line }
}

# --- kiểm tra & chuẩn bị ---
if (-not (Test-Path $BasePath)) {
    throw "BasePath '$BasePath' not exis."
}
# đảm bảo thư mục log tồn tại
if ($LogFile) {
    $lp = Split-Path -Parent $LogFile
    if ($lp -and -not (Test-Path $lp)) { New-Item -ItemType Directory -Force -Path $lp | Out-Null }
}

Write-Log "=== CLEANUP START: BasePath=$BasePath, DB=$Database, Full=$FullDays d, Diff=$DiffDays d, Log=$LogDays d, WhatIf=$WhatIf ==="

# bản đồ loại → (subfolder, extension, days)
$rules = @(
    @{ Type='Full'; Sub='Full'; Ext='.bak'; Days=$FullDays },
    @{ Type='Diff'; Sub='Diff'; Ext='.dif'; Days=$DiffDays },
    @{ Type='Log' ; Sub='Log' ; Ext='.trn'; Days=$LogDays  }
)

# Lấy danh sách DB folder
$dbFolders = @()
if ([string]::IsNullOrWhiteSpace($Database)) {
    $dbFolders = Get-ChildItem -LiteralPath $BasePath -Directory -ErrorAction SilentlyContinue
} else {
    $p = Join-Path $BasePath $Database
    if (-not (Test-Path $p)) {
        Write-Log "DB '$Database' No folder $p to Next."
        exit 0
    }
    $dbFolders = ,(Get-Item -LiteralPath $p)
}

foreach ($db in $dbFolders) {
    Write-Log "-- DB: $($db.Name) --"

    foreach ($r in $rules) {
        $type   = $r.Type
        $sub    = $r.Sub
        $ext    = $r.Ext
        $days   = [int]$r.Days
        $cutoff = (Get-Date).AddDays(-$days)

        $typePath = Join-Path $db.FullName $sub
        if (-not (Test-Path $typePath)) {
            Write-Log "  [$type] No folder: $typePath to next."
            continue
        }

        Write-Log "  [$type] Keep file $days days to delete file *$ext have LastWriteTime < $($cutoff.ToString('yyyy-MM-dd HH:mm:ss'))"

        # Tìm file cần xoá (trong mọi thư mục con YYYYMMDD)
        $toDelete = Get-ChildItem -LiteralPath $typePath -Recurse -File -ErrorAction SilentlyContinue |
                    Where-Object { $_.Extension -ieq $ext -and $_.LastWriteTime -lt $cutoff }

        if (-not $toDelete -or $toDelete.Count -eq 0) {
            Write-Log "    None one files to delete."
        } else {
            foreach ($f in $toDelete) {
                if ($WhatIf) {
                Write-Log "    [DRY-RUN] Would remove: $($f.FullName)"
                } else {
                try {
                    Remove-Item -LiteralPath $f.FullName -Force -ErrorAction Stop
                    Write-Log "    Removed: $($f.FullName)"
                } catch {
                    Write-Log "    Delete file error: $($f.FullName) to $($_.Exception.Message)"
                }
                }
            }
        }

        # Xoá thư mục rỗng (YYYYMMDD) rồi thư mục loại (Full/Diff/Log) nếu rỗng
        # (chỉ nếu không WhatIf)
        if (-not $WhatIf) {
        # Xoá từ dưới lên để dễ rỗng dần
        $emptyDirs = Get-ChildItem -LiteralPath $typePath -Recurse -Directory -ErrorAction SilentlyContinue |
                    Sort-Object FullName -Descending
        foreach ($d in $emptyDirs) {
            try {
                if (-not (Get-ChildItem -LiteralPath $d.FullName -Force -ErrorAction SilentlyContinue)) {
                    Remove-Item -LiteralPath $d.FullName -Force -Recurse -ErrorAction Stop
                    Write-Log "    Removed empty folder: $($d.FullName)"
                }
            } catch {
                Write-Log "    Delete Folder Error: $($d.FullName) to $($_.Exception.Message)"
            }
        }

        # Nếu thư mục loại (Full/Diff/Log) rỗng to xoá
        try {
            if (-not (Get-ChildItem -LiteralPath $typePath -Force -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $typePath -Force -Recurse -ErrorAction Stop
                Write-Log "    Removed empty type folder: $typePath"
            }
        } catch {
            Write-Log "    Error Dlete fordel: $typePath to $($_.Exception.Message)"
            }
        } else {
            Write-Log "    [DRY-RUN] Escape delete folder."
        }
    }
}

Write-Log "=== CLEANUP END ==="
