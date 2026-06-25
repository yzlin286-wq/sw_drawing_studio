$ErrorActionPreference = "Stop"
$exe = "C:\Users\Vision\Desktop\SW 相关\dist\sw_drawing_studio.exe"
$shotDir = "C:\Users\Vision\Desktop\SW 相关\.trae\specs\build-v6-and-validate-exe-ui\screenshots"
New-Item -ItemType Directory -Force -Path $shotDir | Out-Null

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$signature = @'
[DllImport("user32.dll")]
public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")]
public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
[DllImport("user32.dll", SetLastError = true)]
public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
'@
Add-Type -MemberDefinition $signature -Namespace Win32 -Name NativeMethods

function Take-Screenshot($path) {
    $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bmp.Size)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
}

function Bring-ToFront($procId) {
    try {
        $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($p -and $p.MainWindowHandle -ne 0) {
            [Win32.NativeMethods]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
            [Win32.NativeMethods]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
        }
    } catch {}
}

# 启动 EXE
$proc = Start-Process -FilePath "$exe" -PassThru -WorkingDirectory (Split-Path -Parent $exe)
Write-Output "PID=$($proc.Id)"
Start-Sleep -Seconds 7

Bring-ToFront $proc.Id
Start-Sleep -Milliseconds 800

# 01 首页
Take-Screenshot (Join-Path $shotDir "01_home.png")
Write-Output "01_home done"

# 02 批量出图 - 按 Down
Bring-ToFront $proc.Id
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("{DOWN}")
Start-Sleep -Milliseconds 1500
Take-Screenshot (Join-Path $shotDir "02_batch.png")
Write-Output "02_batch done"

# 03 AI 质检
Bring-ToFront $proc.Id
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("{DOWN}")
Start-Sleep -Milliseconds 1500
Take-Screenshot (Join-Path $shotDir "03_qc.png")
Write-Output "03_qc done"

# 04 BOM 与核价
Bring-ToFront $proc.Id
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("{DOWN}")
Start-Sleep -Milliseconds 1500
Take-Screenshot (Join-Path $shotDir "04_bom.png")
Write-Output "04_bom done"

# 05 设置（会弹出对话框）
Bring-ToFront $proc.Id
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("{DOWN}")
Start-Sleep -Milliseconds 2000
Take-Screenshot (Join-Path $shotDir "05_settings.png")
Write-Output "05_settings done"

# 关闭设置对话框
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait("{ESC}")
Start-Sleep -Milliseconds 800

# 06 日志
Bring-ToFront $proc.Id
Start-Sleep -Milliseconds 300
# 当前导航位于 stack.currentIndex 对应的 row（设置被弹回，可能仍是 BOM=3），再连按 Down 两次到日志=5
[System.Windows.Forms.SendKeys]::SendWait("{DOWN}")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{DOWN}")
Start-Sleep -Milliseconds 500
# 跳到日志（关闭设置后，nav 可能仍指向之前的 BOM；需多次 Down 直到 LOG）
[System.Windows.Forms.SendKeys]::SendWait("{DOWN}")
Start-Sleep -Milliseconds 1500
Take-Screenshot (Join-Path $shotDir "06_log.png")
Write-Output "06_log done"

Start-Sleep -Milliseconds 500
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Output "Stopped"

# 列出所有截图大小
Get-ChildItem $shotDir -Filter "*.png" | ForEach-Object {
    $kb = [math]::Round($_.Length / 1024, 1)
    Write-Output ("{0}: {1} KB" -f $_.Name, $kb)
}
