@echo off
setlocal

rem === Paths (relative to this launcher) ===
set "ROOT_DIR=%~dp0"
set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "FRONT_DIR=%ROOT_DIR%\frontend"
set "BACK_DIR=%ROOT_DIR%\backend"

rem === Backend BATs ===
set "AUTH_BAT=%BACK_DIR%\run_auth.bat"
set "WORKER_BAT=%BACK_DIR%\run_worker.bat"
set "MAIN_BAT=%BACK_DIR%\run_main.bat"
set "AI_BAT=%BACK_DIR%\run_ai.bat"

rem === Window titles ===
set "T1=GRID_FRONT_DEV"
set "T2=GRID_AUTH"
set "T3=GRID_WORKER"
set "T4=GRID_MAIN"
set "T5=GRID_AI"

rem === Monitor index (0 = primary, 1 = second) ===
set "MONITOR_INDEX=1"

rem 1) Frontend (top-left)
start "%T1%" cmd /k "title %T1% && cd /d ""%FRONT_DIR%"" && npm run dev"

rem 2) Auth (top-right)
start "%T2%" cmd /k "title %T2% && cd /d ""%BACK_DIR%"" && call ""%AUTH_BAT%"""

rem 3) Worker (bottom-left)
start "%T3%" cmd /k "title %T3% && cd /d ""%BACK_DIR%"" && call ""%WORKER_BAT%"""

rem 4) Main (bottom-right)
start "%T4%" cmd /k "title %T4% && cd /d ""%BACK_DIR%"" && call ""%MAIN_BAT%"""

rem 5) AI (extra)
start "%T5%" cmd /k "title %T5% && cd /d ""%BACK_DIR%"" && call ""%AI_BAT%"""

rem Wait for windows to appear
timeout /t 2 /nobreak >nul

rem === Arrange 3x2 on target monitor ===
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
$log = "$env:TEMP\\launcher_debug.txt"; ^
"--- launcher " + (Get-Date) | Out-File -FilePath $log -Encoding utf8; ^
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class Win {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@; ^
Add-Type -AssemblyName System.Windows.Forms; ^
function Find-WindowByTitle([string]$needle){
  $script:found = [IntPtr]::Zero;
  [Win]::EnumWindows({ param($h, $l)
    if(-not [Win]::IsWindowVisible($h)){ return $true }
    $len = [Win]::GetWindowTextLength($h);
    if($len -le 0){ return $true }
    $sb = New-Object System.Text.StringBuilder ($len + 1);
    [void][Win]::GetWindowText($h, $sb, $sb.Capacity);
    $t = $sb.ToString();
    if($t -like "*$needle*"){ $script:found = $h; return $false }
    return $true
  }, [IntPtr]::Zero) | Out-Null;
  return $script:found
}; ^
$monitors = [System.Windows.Forms.Screen]::AllScreens; ^
"monitors=" + $monitors.Count | Out-File -FilePath $log -Append; ^
for($i=0; $i -lt $monitors.Count; $i++){
  $m = $monitors[$i];
  ("monitor[{0}]={1} bounds={2}" -f $i, $m.DeviceName, $m.Bounds) | Out-File -FilePath $log -Append;
} ^
$idx = [int]('%MONITOR_INDEX%'); ^
$target = if($monitors.Count -gt $idx){ $monitors[$idx] } else { $monitors[0] }; ^
$wa = $target.WorkingArea; ^
$("target=" + $target.DeviceName + " wa=" + $wa) | Out-File -FilePath $log -Append; ^
$w = [int]($wa.Width / 3); ^
$h = [int]($wa.Height / 2); ^
$pos = @(
  @{title='%T1%'; x=$wa.X;          y=$wa.Y       },
  @{title='%T2%'; x=$wa.X + $w;     y=$wa.Y       },
  @{title='%T4%'; x=$wa.X + $w*2;   y=$wa.Y       },
  @{title='%T3%'; x=$wa.X;          y=$wa.Y + $h  },
  @{title='%T5%'; x=$wa.X + $w;     y=$wa.Y + $h  }
); ^
foreach($p in $pos){
  $hwnd = [IntPtr]::Zero;
  for($i=0; ($hwnd -eq [IntPtr]::Zero) -and ($i -lt 60); $i++){
    Start-Sleep -Milliseconds 200;
    $hwnd = Find-WindowByTitle $p.title;
  }
  ("find '" + $p.title + "' => " + $hwnd) | Out-File -FilePath $log -Append;
  if($hwnd -ne [IntPtr]::Zero){
    [Win]::MoveWindow($hwnd, $p.x, $p.y, $w, $h, $true) | Out-Null
  }
}; ^
$hw = Find-WindowByTitle '%T1%'; if($hw -ne [IntPtr]::Zero){ [Win]::SetForegroundWindow($hw) | Out-Null }

exit /b
