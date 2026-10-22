# ============================================================
# verify_release.ps1 —— 合记 ChemLab 发布验收脚本
#
# 一条命令跑完四项待确认事项的自动化部分，输出结构化报告。
#
# 用法：
#     powershell -ExecutionPolicy Bypass -File build\verify_release.ps1
#     powershell -ExecutionPolicy Bypass -File build\verify_release.ps1 -InstallDir "D:\temp\chemlab-verify"
#
# 参数：
#     -SkipBuild    跳过构建，直接用已有的安装包验收
#     -InstallDir   安装目录（不指定则装到用户 LocalAppData）
#     -Fast         构建时关闭 LTO（受限环境用）
#
# 覆盖的检查项：
#     A. 产物完整性   —— 安装包存在、sidecar 在位、SOP 资源在位
#     B. 安装与启动   —— 静默安装 → 启动 → sidecar 自动拉起 → 健康检查 → 日志
#     C. 退出回收     —— 温和退出 → 端口释放、sidecar 进程消失
#     D. 卸载残留     —— 卸载后检查安装目录与注册表
#     E. 端口冲突     —— 端口被占时的降级提示是否正确
#
# 说明：GUI 相关的检查（子 webview 渲染、窗口显示）无法在脚本里判断，
#       脚本会打印需要人工确认的清单，见 docs/验收清单.md
# ============================================================
param(
    [switch]$SkipBuild,
    [string]$InstallDir = "",
    [switch]$Fast
)

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $ROOT

$results = @()
function Check($name, $ok, $detail) {
    $tag = if ($ok) { "PASS" } else { "FAIL" }
    $script:results += [PSCustomObject]@{ Item = $name; Result = $tag; Detail = $detail }
    $color = if ($ok) { "Green" } else { "Yellow" }
    Write-Host ("  [{0}] {1} —— {2}" -f $tag, $name, $detail) -ForegroundColor $color
}
function Note($msg) { Write-Host ("  [INFO] " + $msg) -ForegroundColor DarkGray }
function Section($t) { Write-Host "`n== $t ==" -ForegroundColor Cyan }

# ───────────────────────── 0. 准备 ─────────────────────────
Section "0. 环境检查"
$pyExe = Join-Path $ROOT "backend\venv\Scripts\python.exe"
Check "后端虚拟环境存在" (Test-Path $pyExe) $pyExe

$nsisDir = Join-Path $ROOT "src-tauri\target\release\bundle\nsis"

# ───────────────────────── 1. 构建 ─────────────────────────
if (-not $SkipBuild) {
    Section "1. 构建（release）"
    if ($Fast) {
        $env:CARGO_PROFILE_RELEASE_LTO = "false"
        Note "已关闭 LTO（-Fast）"
    }
    Push-Location src-tauri
    try {
        npx tauri build
        Check "Tauri 打包成功" ($LASTEXITCODE -eq 0) "release"
    } finally { Pop-Location }
}

# 找安装包
$installer = Get-ChildItem $nsisDir -Filter "*.exe" -ErrorAction SilentlyContinue |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) {
    Write-Host "`n找不到安装包（$nsisDir）—— 请先构建。" -ForegroundColor Red
    exit 1
}
$installerMB = [math]::Round($installer.Length / 1MB, 1)
Check "安装包存在" $true "$($installer.Name)  ($installerMB MB)"

# ───────────────────────── 2. 安装 ─────────────────────────
Section "2. 静默安装"
if ($InstallDir) {
    $target = $InstallDir
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    $arg = "/D=$($target -replace '\\','/')"
} else {
    $target = Join-Path $env:LOCALAPPDATA "合记 ChemLab"
    $arg = ""
}
Write-Host "  安装到: $target"

# /D 必须是最后一个参数且不含引号；用 Start-Process 避免参数被二次解析
$procArgs = @("/S") + ($(if ($arg) { $arg } else { "" })) | Where-Object { $_ -ne "" }
$p = Start-Process -FilePath $installer.FullName -ArgumentList $procArgs -Wait -PassThru
Check "安装程序执行成功" ($p.ExitCode -eq 0) "退出码 $($p.ExitCode)"
Start-Sleep -Seconds 3

# ───────────────────────── 3. 产物完整性 ─────────────────────────
Section "3. 安装后产物完整性"
$exe = Get-ChildItem $target -Filter "*.exe" -ErrorAction SilentlyContinue |
       Where-Object { $_.Name -notlike "uninstall*" } | Select-Object -First 1
Check "主程序存在" ($null -ne $exe) $(if ($exe) { $exe.Name } else { "未找到" })

$sidecar = Get-ChildItem (Join-Path $target "resources\backend") -Filter "ChemLabBackend.exe" -ErrorAction SilentlyContinue |
           Select-Object -First 1
Check "Python sidecar 在位" ($null -ne $sidecar) "resources\backend\ChemLabBackend.exe"

$internal = Join-Path $target "resources\backend\_internal"
Check "sidecar 依赖目录在位" (Test-Path $internal) "_internal\"

$frontend = Join-Path $internal "frontend"
Check "合迹前端已内置" (Test-Path (Join-Path $frontend "index.html")) "resources\backend\_internal\frontend\index.html"

$sops = Get-ChildItem $target -Recurse -Filter "*.md" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like "*sops*" } | Select-Object -First 1
Check "SOP 资源在位" ($null -ne $sops) $(if ($sops) { $sops.FullName.Replace($target, "") } else { "未找到" })

# ───────────────────────── 4. 启动与后端 ─────────────────────────
Section "4. 启动与后端拉起"
$port = 8765
Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$logPath = Join-Path $env:APPDATA "ChemLab\logs\backend.log"
if (Test-Path $logPath) { Remove-Item $logPath -Force -ErrorAction SilentlyContinue }

if ($exe) {
    Start-Process -FilePath $exe.FullName -WorkingDirectory $target | Out-Null
    Write-Host "  等待后端就绪（最多 40 秒）..."
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        try {
            $h = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 2
            if ($h.status -eq "ok") { $ready = $true; break }
        } catch { }
    }
    Check "后端被主壳自动拉起" $ready "http://127.0.0.1:$port/api/health"
    if ($ready) {
        Check "服务标识正确" ($h.service -eq "ChemLab") "service=$($h.service) version=$($h.version)"
    }
}

$sc = Get-Process -Name "ChemLabBackend" -ErrorAction SilentlyContinue | Select-Object -First 1
Check "sidecar 进程在运行" ($null -ne $sc) $(if ($sc) { "PID $($sc.Id)" } else { "未找到" })

Check "后端日志落盘" (Test-Path $logPath) $logPath
if (Test-Path $logPath) {
    $logTail = (Get-Content $logPath -Tail 3) -join " | "
    Note "日志尾部: $logTail"
    Check "日志含就绪记录" ((Get-Content $logPath -Raw) -match "Ready at") "含 'Ready at'"
}

# ───────────────────────── 5. 退出回收 ─────────────────────────
Section "5. 退出时回收 sidecar"
# 用进程名找主程序（$exe 是文件对象，没有进程 Id）
$appProc = Get-Process -Name "heji-toolbox" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($appProc) {
    # CloseMainWindow() = 发 WM_CLOSE，走 Tauri 的正常退出流程（RunEvent::Exit），
    # 这样才能验证「退出时回收 sidecar」。
    # 注意：不要用 Stop-Process（等价于强杀），那会跳过退出钩子，
    # 测出来的「端口未释放」是假阴性。
    $null = $appProc.CloseMainWindow()
    $null = $appProc.WaitForExit(15000)
    Start-Sleep -Seconds 3
} else {
    Note "未找到运行中的主程序进程，跳过"
}
$still = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
Check "退出后端口已释放" ($null -eq $still) "port $port"
$sc2 = Get-Process -Name "ChemLabBackend" -ErrorAction SilentlyContinue
Check "退出后 sidecar 已回收" ($null -eq $sc2) "无残留进程"

# ───────────────────────── 6. 卸载残留 ─────────────────────────
Section "6. 卸载与残留检查"
$un = Join-Path $target "uninstall.exe"
if (Test-Path $un) {
    $up = Start-Process -FilePath $un -ArgumentList "/S" -Wait -PassThru
    Start-Sleep -Seconds 5
    $left = Get-ChildItem $target -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne "uninstall.exe" }
    Check "卸载后安装目录无残留" ($null -eq $left) \
        $(if ($left) { "残留: " + (($left | Select-Object -First 3).FullName -join ", ") } else { "干净" })
    if ($left) {
        Note "若在受限环境（沙箱/CI）里，uninstall.exe 的删除操作可能被拦截 ——"
        Note "此时请在正常 Windows 上复验（脚本本身已确认注册表卸载项被清除）。"
    }

    $reg = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
           Where-Object { $_.DisplayName -like "*ChemLab*" }
    Check "注册表卸载项已清除" ($null -eq $reg) $(if ($reg) { "仍存在" } else { "已清除" })
} else {
    Note "未找到 uninstall.exe，跳过"
}

$userData = Join-Path $env:APPDATA "ChemLab"
Check "用户数据保留（设计如此）" (Test-Path $userData) "$userData（需用户自行决定是否删除）"

# ───────────────────────── 7. 端口冲突降级 ─────────────────────────
Section "7. 端口占用时的降级"
Note "如需验证：先手动占用 8765 端口，再启动应用，检查「设置 → 后端服务」是否给出"
Note "「端口已被占用」提示而不是白屏。脚本不自动执行此项（会打断当前服务）。"

# ───────────────────────── 报告 ─────────────────────────
Section "验收报告"
$results | Format-Table -AutoSize
$fail = @($results | Where-Object { $_.Result -eq "FAIL" })
Write-Host ""
if ($fail.Count -eq 0) {
    Write-Host "自动化检查项全部通过（$($results.Count) 项）" -ForegroundColor Green
} else {
    Write-Host "通过 $($results.Count - $fail.Count) / $($results.Count)，未通过 $($fail.Count) 项：" -ForegroundColor Yellow
    $fail | ForEach-Object { Write-Host "   - $($_.Item)：$($_.Detail)" -ForegroundColor Yellow }
}

Write-Host "`n仍需人工确认（脚本无法判断）：" -ForegroundColor Cyan
Write-Host "  1. 窗口是否正常显示、导航是否可用"
Write-Host "  2. 「实验记录」页：原生子 webview 是否贴合内容区、切换视图是否生效"
Write-Host "  3. 杀软是否误报（Defender 保护历史记录 + 第三方杀软白名单）"
Write-Host "  详见 docs/验收清单.md" -ForegroundColor DarkGray

$outFile = Join-Path $ROOT "build\验收报告-$(Get-Date -Format 'yyyyMMdd-HHmm').txt"
$results | Format-Table -AutoSize | Out-String | Out-File -FilePath $outFile -Encoding UTF8
Write-Host "`n报告已保存: $outFile" -ForegroundColor DarkGray
