$ErrorActionPreference = "Stop"
$exe = "C:\Users\Vision\Desktop\SW 相关\dist\sw_drawing_studio.exe"
$shotDir = "C:\Users\Vision\Desktop\SW 相关\.trae\specs\build-3d-to-2d-desktop-app\screenshots"
New-Item -ItemType Directory -Force -Path $shotDir | Out-Null

Write-Output "ExeExists=$(Test-Path -LiteralPath $exe)"

$t0 = Get-Date
$proc = Start-Process -FilePath "$exe" -PassThru -WorkingDirectory (Split-Path -Parent $exe)
Write-Output "PID=$($proc.Id)"

Start-Sleep -Seconds 6

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bmp.Size)
$shot1 = Join-Path $shotDir "01_main_window.png"
$bmp.Save($shot1, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
Write-Output "Screenshot1=$shot1"

$elapsedMs = [int]((Get-Date) - $t0).TotalMilliseconds
Write-Output "ElapsedMs=$elapsedMs"

$running = Get-Process -Name sw_drawing_studio -ErrorAction SilentlyContinue
if ($running) {
    Write-Output "ProcessAlive=YES Count=$($running.Count)"
} else {
    Write-Output "ProcessAlive=NO"
}

Start-Sleep -Seconds 1
Stop-Process -Name sw_drawing_studio -Force -ErrorAction SilentlyContinue
Write-Output "Stopped"
