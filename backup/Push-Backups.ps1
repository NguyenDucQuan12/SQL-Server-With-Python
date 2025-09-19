param(
    [Parameter(Mandatory=$true)] [string]$SourceBase = "E:\SQL_Backup",
    [Parameter(Mandatory=$true)] [string]$DestBase   = "\\FILESERV\SQL_Backup",
    [Parameter(Mandatory=$false)][string[]]$Types    = @("Full","Diff","Log"),
    [Parameter(Mandatory=$false)][string]$Database,           # optional: push 1 DB
    [int]$Threads = 8,
    [int]$Retries = 3,
    [int]$RetryWaitSec = 5,
    [int]$PerCopyTimeoutSec = 300,
    [string]$LogFile = "C:\Scripts\push-backups.log"
)

# --- Normalize $Types: accept "Full,Diff,Log" or array ---
if ($null -ne $Types -and $Types.Count -eq 1 -and $Types[0] -match ',') {
    $Types = $Types[0].Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}
# (tùy chọn) ép về các giá trị hợp lệ, phòng case sai:
$valid = @('full','diff','log')
$Types = $Types | ForEach-Object { $_.Trim() } | Where-Object { $valid -contains $_.ToLower() }
if (-not $Types -or $Types.Count -eq 0) {
    Write-Host "No valid -Types provided. Defaulting to Full,Diff,Log."
    $Types = @('Full','Diff','Log')
}

function Write-Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    if ($LogFile) {
        $dir = Split-Path -Parent $LogFile
        if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        Add-Content -Path $LogFile -Value $line
    }
}

function Test-DestinationReady {
    param([string]$path)
    try {
        if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
        }
        $probe = Join-Path $path (".probe_{0}.tmp" -f [guid]::NewGuid())
        Set-Content -LiteralPath $probe -Value "probe" -ErrorAction Stop
        Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
        return $true
    } catch {
        Write-Log ("Destination NOT ready or write denied: {0} -> {1}" -f $path, $_.Exception.Message)
        return $false
    }
}

function Invoke-RoboCopy {
    <#
        Chạy robocopy có kiểm soát timeout; trả về $true nếu coi là thành công
        Exit code robocopy: 0–7 = OK/Cảnh báo, >=8 = lỗi
    #>
    param(
        [string]$srcDir,
        [string]$dstDir,
        [string]$fileMask,      # *.bak | *.dif | *.trn | *.*
        [int]$timeoutSec = 300  # 0 hoặc âm = không giới hạn
    )

    if (-not (Test-Path -LiteralPath $srcDir -PathType Container)) {
        Write-Log ("Source folder not found: {0} (skip)" -f $srcDir)
        return $true
    }
    if (-not (Test-Path -LiteralPath $dstDir -PathType Container)) {
        try {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
        } catch {
        Write-Log ("Cannot create destination: {0} -> {1}" -f $dstDir, $_.Exception.Message)
        return $false
        }
    }

    $args = @(
        "`"$srcDir`"", "`"$dstDir`"", $fileMask,
        "/Z", "/FFT", "/XO",
        "/R:$Retries", "/W:$RetryWaitSec",
        "/MT:$Threads",
        "/NP", "/NFL", "/NDL",
        "/TEE"
    )
    $logTmp = Join-Path $env:TEMP ("robocopy_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
    $args += "/LOG:$logTmp"

    Write-Log ("ROBO: ""{0}"" -> ""{1}"" ({2})" -f $srcDir, $dstDir, $fileMask)

    # Khởi chạy và chờ đúng kiểu .NET
    $p = Start-Process -FilePath "robocopy.exe" -ArgumentList $args -PassThru -WindowStyle Hidden

    try {
        if ($timeoutSec -le 0) {
        # Không giới hạn: chờ đến khi kết thúc
        $null = $p.WaitForExit()
        } else {
        $exited = $p.WaitForExit([int]($timeoutSec * 1000))
        if (-not $exited) {
            Write-Log ("Timeout {0}s. Killing robocopy PID {1}" -f $timeoutSec, $p.Id)
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            return $false
        }
        }

        $exit = $p.ExitCode
        if ($exit -ge 8) {
        Write-Log ("Robocopy failed (exit {0}). See {1}" -f $exit, $logTmp)
        return $false
        } else {
        # 0: nothing to copy; 1: copied; 2–7: warnings but usually acceptable
        Write-Log ("Robocopy done (exit {0})." -f $exit)
        return $true
        }
    } catch {
        Write-Log ("Robocopy exception: {0}" -f $_.Exception.Message)
        return $false
    }
}

# ---------------- Main ----------------
Write-Log ("=== PUSH START: {0} -> {1} | Types: {2} ===" -f $SourceBase, $DestBase, ($Types -join ","))

# Check destination root
if (-not (Test-DestinationReady -path $DestBase)) {
    Write-Log "Destination not ready. Skip this run."
    exit 0
}

# Check source base
if (-not (Test-Path -LiteralPath $SourceBase -PathType Container)) {
    Write-Log ("SourceBase not found: {0}" -f $SourceBase)
    exit 0
}

# Collect DB dirs
$dbDirs = @()
if ([string]::IsNullOrWhiteSpace($Database)) {
    $dbDirs = Get-ChildItem -LiteralPath $SourceBase -Directory -ErrorAction SilentlyContinue
    if (-not $dbDirs -or $dbDirs.Count -eq 0) {
        Write-Log "No database subfolders under SourceBase. Nothing to push."
        Write-Log "Tip: expected structure is <SourceBase>\<DB>\<Full|Diff|Log>\<YYYYMMDD>\files"
        Write-Log "=== PUSH END ==="
        exit 0
    }
} else {
    $one = Join-Path $SourceBase $Database
    if (Test-Path -LiteralPath $one -PathType Container) {
        $dbDirs = ,(Get-Item -LiteralPath $one)
    } else {
        Write-Log ("Database folder not found: {0}" -f $one)
        Write-Log "=== PUSH END ==="
        exit 0
    }
}

Write-Log ("DBs found: {0}" -f (($dbDirs | Select-Object -ExpandProperty Name) -join ", "))

foreach ($db in $dbDirs) {
    Write-Log ("-- DB: {0}" -f $db.Name)
    foreach ($t in $Types) {
        $srcType = Join-Path $db.FullName $t
        if (-not (Test-Path -LiteralPath $srcType -PathType Container)) {
            Write-Log ("  Type folder not found: {0} (skip)" -f $srcType)
            continue
        }

        # Map extension by type
        switch ($t.ToLower()) {
            "full" { $mask = "*.bak" }
            "diff" { $mask = "*.dif" }
            "log"  { $mask = "*.trn" }
            default { $mask = "*.*" }
        }

        # Prefer day subfolders
        $dayDirs = Get-ChildItem -LiteralPath $srcType -Directory -ErrorAction SilentlyContinue | Sort-Object Name
        if ($dayDirs -and $dayDirs.Count -gt 0) {
            Write-Log ("  Type={0} days: {1}" -f $t, (($dayDirs | Select-Object -ExpandProperty Name) -join ", "))
            foreach ($dayDir in $dayDirs) {
                $dstDay = Join-Path (Join-Path (Join-Path $DestBase $db.Name) $t) $dayDir.Name
                if (-not (Test-DestinationReady -path $dstDay)) {
                    Write-Log ("  Destination subfolder not ready: {0} (skip this day)" -f $dstDay)
                    continue
                }
                [void](Invoke-RoboCopy -srcDir $dayDir.FullName -dstDir $dstDay -fileMask $mask -timeoutSec $PerCopyTimeoutSec)
            }
        } else {
            # Fallback: no day folders -> push files directly from type folder
            Write-Log ("  Type={0} has no day folders. Fallback: push files in {1}" -f $t, $srcType)
            $dstType = Join-Path (Join-Path $DestBase $db.Name) $t
            if (-not (Test-DestinationReady -path $dstType)) {
                Write-Log ("  Destination type folder not ready: {0} (skip)" -f $dstType)
                continue
            }
            [void](Invoke-RoboCopy -srcDir $srcType -dstDir $dstType -fileMask $mask -timeoutSec $PerCopyTimeoutSec)
        }
    }
}

Write-Log "=== PUSH END ==="
