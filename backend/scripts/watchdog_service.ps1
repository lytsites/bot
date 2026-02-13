param(
    [string]$BackendDir = "",
    [string]$ServiceBat = "",
    [string]$ProcessPattern = "",
    [string]$CheckUrl = "",
    [int]$IntervalSec = 15,
    [int]$FailThreshold = 3,
    [int]$RequestTimeoutSec = 8,
    [string]$LogName = "service_watchdog.log"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($BackendDir)) {
    $BackendDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if ([string]::IsNullOrWhiteSpace($ServiceBat)) {
    throw "ServiceBat is required"
}
if ([string]::IsNullOrWhiteSpace($ProcessPattern)) {
    throw "ProcessPattern is required"
}

$serviceBatPath = Join-Path $BackendDir $ServiceBat
$logDir = Join-Path $BackendDir "var\logs"
$logPath = Join-Path $logDir $LogName

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log([string]$message) {
    $line = ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message)
    Add-Content -Path $logPath -Value $line
    Write-Output $line
}

function Get-ServiceProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -match "^python(\.exe)?$" -or $_.Name -ieq "py.exe") -and
        ($_.CommandLine -like "*$ProcessPattern*")
    }
}

function Test-ServiceHealthy {
    if ([string]::IsNullOrWhiteSpace($CheckUrl)) {
        return (@(Get-ServiceProcesses).Count -gt 0)
    }
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $CheckUrl -TimeoutSec $RequestTimeoutSec
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Stop-ServiceProcess {
    $procs = @(Get-ServiceProcesses)
    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            Write-Log ("stop pid={0}" -f $p.ProcessId)
        } catch {
            Write-Log ("stop failed pid={0} err={1}" -f $p.ProcessId, $_.Exception.Message)
        }
    }
}

function Start-ServiceProcess {
    if (-not (Test-Path $serviceBatPath)) {
        throw "Missing file: $serviceBatPath"
    }
    if (@(Get-ServiceProcesses).Count -gt 0) {
        return
    }
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$BackendDir`" && call `"$serviceBatPath`"" -WindowStyle Minimized | Out-Null
    Write-Log ("start service bat={0}" -f $ServiceBat)
}

Write-Log ("watchdog started backend={0} service={1} pattern={2} check_url={3}" -f $BackendDir, $ServiceBat, $ProcessPattern, $CheckUrl)

$failCount = 0
while ($true) {
    if (Test-ServiceHealthy) {
        if ($failCount -gt 0) {
            Write-Log "health recovered"
        }
        $failCount = 0
    } else {
        $failCount += 1
        Write-Log ("health fail {0}/{1}" -f $failCount, $FailThreshold)
    }

    if ($failCount -ge $FailThreshold) {
        Write-Log "restart service"
        Stop-ServiceProcess
        Start-Sleep -Seconds 2
        Start-ServiceProcess
        Start-Sleep -Seconds 4
        $failCount = 0
    } elseif (@(Get-ServiceProcesses).Count -eq 0) {
        Write-Log "process missing; start"
        Start-ServiceProcess
    }

    Start-Sleep -Seconds $IntervalSec
}
