param(
    [string]$WindowTitleLike = "*",
    [string]$Keys = "{ENTER}"
)

# 向匹配标题的窗口发送按键序列（用于驱动 NSIS 安装向导）
Add-Type -AssemblyName System.Windows.Forms

if (-not ("KeySend" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class KeySend {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
"@
}

$w = Get-Process | Where-Object { $_.MainWindowTitle -like $WindowTitleLike } | Select-Object -First 1
if (-not $w) { Write-Output "未找到匹配 '$WindowTitleLike' 的窗口"; exit 1 }

[void][KeySend]::ShowWindow($w.MainWindowHandle, 9)
[void][KeySend]::SetForegroundWindow($w.MainWindowHandle)
Start-Sleep -Milliseconds 700
[System.Windows.Forms.SendKeys]::SendWait($Keys)
Write-Output ("已向 '" + $w.MainWindowTitle + "' 发送: " + $Keys)
