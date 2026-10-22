<#
.SYNOPSIS
    截取指定窗口的内容为 PNG。

.DESCRIPTION
    用于在无法目视的自动化环境里验证 GUI 表现
    （例如 NSIS 安装向导的语言、子 webview 的渲染）。

    关键点：用 PrintWindow(..., PW_RENDERFULLCONTENT) 直接抓窗口内容，
    而不是 CopyFromScreen —— 后者会被「窗口被遮挡」或「窗口在离屏位置」影响，
    截出来的是别的窗口（本项目就踩过：抓到的是聊天软件的悬浮窗）。

.PARAMETER Out
    输出 PNG 路径。

.PARAMETER WindowTitleLike
    窗口标题的通配符。留空则只列出所有带标题的窗口，不截图。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\screenshot.ps1
    powershell -ExecutionPolicy Bypass -File scripts\screenshot.ps1 -Out D:\tmp\a.png -WindowTitleLike "*Setup*"
#>
param(
    [string]$Out = "D:\tmp\shot.png",
    [string]$WindowTitleLike = ""
)

Add-Type -AssemblyName System.Drawing

if (-not ("Win32Api" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Drawing;
public class Win32Api {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
    public static string Title(IntPtr h) {
        int len = GetWindowTextLength(h);
        if (len <= 0) return "";
        var sb = new System.Text.StringBuilder(len + 2);
        GetWindowText(h, sb, sb.Capacity);
        return sb.ToString();
    }
}
"@
}

$target = $null
foreach ($p in (Get-Process | Where-Object { $_.MainWindowHandle -ne 0 })) {
    $t = [Win32Api]::Title($p.MainWindowHandle)
    if (-not $t) { continue }
    if ($WindowTitleLike) {
        if ($t -like $WindowTitleLike) { $target = $p; break }
    } else {
        Write-Output ("窗口: PID=" + $p.Id + "  '" + $t + "'")
    }
}

if ($WindowTitleLike) {
    if (-not $target) { Write-Output "未找到匹配 '$WindowTitleLike' 的窗口"; exit 1 }
    Write-Output ("找到: PID=" + $target.Id + "  '" + [Win32Api]::Title($target.MainWindowHandle) + "'")
    [void][Win32Api]::ShowWindow($target.MainWindowHandle, 9)   # SW_RESTORE
    [void][Win32Api]::SetForegroundWindow($target.MainWindowHandle)
    Start-Sleep -Milliseconds 800
}

$h = $target.MainWindowHandle
$r = New-Object Win32Api+RECT
[void][Win32Api]::GetWindowRect($h, [ref]$r)
$w = $r.Right - $r.Left
$ht = $r.Bottom - $r.Top
if ($w -le 0 -or $ht -le 0) { Write-Output "窗口尺寸异常: ${w}x${ht}"; exit 1 }

$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
# PrintWindow(..., 2 = PW_RENDERFULLCONTENT) 直接抓窗口内容，
# 不受「窗口被别的窗口盖住」或「窗口在离屏位置」影响。
[void][Win32Api]::PrintWindow($h, $hdc, 2)
$g.ReleaseHdc($hdc)
$g.Dispose()

$dir = Split-Path -Parent $Out
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output ("saved: " + $Out + "  (" + $w + "x" + $ht + ")")
