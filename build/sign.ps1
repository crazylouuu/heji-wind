# ============================================================================
# sign.ps1 —— 自签名工具（当前发布流程不使用）
#
# 【2026-10-27 状态】本项目已决定**不对发布包签名**。
#   原因：自签名证书的信任是「点对点」的 —— 只对愿意手动导入 .cer 的人有效。
#   开源后下载者不认识作者，不会为一个软件去改自己的证书存储，
#   所以对他们来说「自签名」和「没签名」效果相同（一样弹警告，还多一步困惑）。
#   GitHub 上绝大多数开源 Windows 应用都不签名，靠「源码可审计」建立信任。
#
#   发布流程因此保持 build.ps1 默认不签名（-Sign 参数仍在，需要时可用）。
#
#   这个脚本保留下来，仅用于以下场景：
#     · 只分发给内部同事，且愿意让他们导入一次 .cer
#     · 将来购买了商业 OV/EV 证书，可以把这里的自签名替换成商业证书
#
# 以下为原说明：
#
# 用法（在仓库根目录执行）：
#     powershell -ExecutionPolicy Bypass -File build\sign.ps1
#
# 会做什么：
#   1. 在「当前用户」证书存储里创建/复用一个自签名代码签名证书
#      （名称固定为 ChemLab-CodeSigning，便于重复使用与导出）
#   2. 对以下产物签名：
#        src-tauri\target\release\bundle\nsis\*.exe      （安装包）
#        src-tauri\target\release\heji-toolbox.exe        （主程序）
#        src-tauri\resources\backend\ChemLabBackend.exe  （后端 sidecar）
#   3. 导出证书公钥为 .cer，并打印同事侧「信任此证书」的安装步骤
#
# 重要说明：
#   自签名证书（self-signed）**不能**像商业 OV/EV 证书那样自动获得信任。
#   它的价值是：
#     · 消除 Windows SmartScreen 的「未知发布者」黄色提示条
#     · 给启发式引擎一个可校验的签名特征，显著降低误报概率
#     · 同事只需导入一次 .cer 就能永久信任，不必每次手工放行
#   如果要真正做到「双击就装、任何人都不用管证书」，仍需购买
#   OV/EV 代码签名证书（年费数千元），见 docs\杀软误报说明.md 方案 C。
# ============================================================================

param(
    # 证书主题里的组织名，会显示在 Windows 的「属性 → 数字签名」里
    [string]$Subject = "ChemLab",
    # 有效期（年）
    [int]$ValidYears = 5,
    # 跳过签名（只生成证书，用于先看看证书长什么样）
    [switch]$CertOnly,
    # 顺便把自签名证书加入本机「受信任的根证书颁发机构」
    # （这样本机查看签名会显示「有效」；需要管理员权限）
    [switch]$TrustLocal
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "    [!] $msg"  -ForegroundColor Yellow }

# ---------------------------------------------------------------- 1. 证书
Write-Step "准备代码签名证书（自签名）"

$certName = "ChemLab-CodeSigning"
$cert = Get-ChildItem Cert:\CurrentUser\My -ErrorAction SilentlyContinue |
        Where-Object { $_.Subject -like "CN=$certName*" } |
        Select-Object -First 1

if ($cert -and $cert.NotAfter -gt (Get-Date)) {
    Write-Ok "复用已有证书：$($cert.Subject)  （有效期至 $($cert.NotAfter.ToString('yyyy-MM-dd'))）"
} else {
    Write-Host "    创建新证书（有效期 $ValidYears 年）..."
    $cert = New-SelfSignedCertificate `
        -Subject "CN=$certName, O=$Subject" `
        -Type CodeSigningCert `
        -KeyUsage DigitalSignature `
        -KeyAlgorithm RSA `
        -KeyLength 3072 `
        -HashAlgorithm SHA256 `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears($ValidYears)
    Write-Ok "已创建证书：$($cert.Subject)"
}

# 导出公钥（给同事导入用）
$cerPath = Join-Path $ROOT "build\ChemLab-CodeSigning.cer"
Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null
Write-Ok "证书公钥已导出：$cerPath"

# 可选：把自签名根加入本机受信任根，使本机校验显示「有效」
if ($TrustLocal) {
    Write-Step "把自签名证书加入本机「受信任的根证书颁发机构」"
    # 用 certutil 而不是 X509Store.Add()：
    #   .NET 的 Add() 会弹出一个「你确认要安装此证书吗」的安全对话框，
    #   在无人值守/脚本场景下会直接把脚本挂起（表现为输出卡住不返回）。
    #   certutil -addstore -f 是静默的，且能返回明确的退出码。
    & certutil -addstore -f -user Root $cerPath 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "已加入本机受信任根（本机查看签名将显示「有效」）"
    } else {
        Write-Warn2 "加入受信任根失败（certutil 退出码 $LASTEXITCODE）"
        Write-Warn2 "这不影响安装包本身，只影响本机查看签名时的显示。"
        Write-Warn2 "可手动执行（管理员 PowerShell）："
        Write-Warn2 "  certutil -addstore -f -user Root `"$cerPath`""
    }
}

if ($CertOnly) {
    Write-Host "`n已按 -CertOnly 跳过签名。`n"
    exit 0
}

# ---------------------------------------------------------------- 2. 签名
Write-Step "签名产物"

# 要签的文件：存在的才签
$targets = @(
    (Join-Path $ROOT "src-tauri\target\release\bundle\nsis\*.exe"),
    (Join-Path $ROOT "src-tauri\target\release\heji-toolbox.exe"),
    (Join-Path $ROOT "src-tauri\resources\backend\ChemLabBackend.exe")
)

$signed = 0
$failed = 0
foreach ($pattern in $targets) {
    $files = Get-ChildItem -Path $pattern -File -ErrorAction SilentlyContinue
    if (-not $files) {
        Write-Warn2 "跳过（无产物）：$pattern"
        continue
    }
    foreach ($f in $files) {
        # 签名时会短暂占用文件，Defender 可能短暂锁住 —— 重试几次
        $ok = $false
        $lastStatus = ""
        for ($i = 1; $i -le 3 -and -not $ok; $i++) {
            try {
                $sig = Set-AuthenticodeSignature -FilePath $f.FullName `
                        -Certificate $cert `
                        -HashAlgorithm SHA256 `
                        -TimestampServer "http://timestamp.digicert.com"
                $lastStatus = $sig.Status
                # 判定「签名是否真的写进去了」的标准是 SignerCertificate 存在，
                # 而不是 Status == Valid —— 自签名证书的 Status 必然是
                # UnknownError（链终止于不受信任的根），但签名本身完全有效。
                if ($sig.SignerCertificate -and $sig.Status -ne "NotSigned" -and
                    $sig.Status -ne "HashMismatch" -and $sig.Status -ne "UnknownError") {
                    $ok = $true
                } elseif ($sig.SignerCertificate -and $sig.Status -eq "UnknownError") {
                    $ok = $true   # 自签名的预期结果
                } elseif ($sig.SignerCertificate) {
                    Write-Warn2 "  $($f.Name) 签名状态：$($sig.Status)（第 $i 次）"
                }
            } catch {
                Write-Warn2 "  $($f.Name) 签名异常：$($_.Exception.Message)（第 $i 次）"
            }
            if (-not $ok) { Start-Sleep -Seconds 2 }
        }
        if ($ok) {
            Write-Ok "已签名：$($f.Name)  ($([math]::Round($f.Length/1MB,1)) MB)"
            $signed++
        } else {
            Write-Warn2 "签名失败：$($f.Name)  (最后状态: $lastStatus)"
            $failed++
        }
    }
}

# ---------------------------------------------------------------- 3. 校验
Write-Step "校验签名状态"
Write-Host "    提示：自签名证书的 Status 显示 UnknownError 属正常 ——" -ForegroundColor DarkGray
Write-Host "    意思是「链终止于不受信任的根」，只要 SignerCertificate 存在即签名有效。" -ForegroundColor DarkGray
Write-Host ""
Get-ChildItem -Path $targets -File -ErrorAction SilentlyContinue | ForEach-Object {
    $s = Get-AuthenticodeSignature $_.FullName
    $stamp = if ($s.TimeStamperCertificate) { "有DigiCert时间戳" } else { "无时间戳" }
    # 注意：变量名不能叫 $signed —— 那是外层的成功计数，会被覆盖
    $signState = if ($s.SignerCertificate) { "已签名" } else { "未签名" }
    Write-Host ("    {0,-52} {1}  签名={2}  {3}" -f $_.Name, $s.Status, $signState, $stamp)
}

# ---------------------------------------------------------------- 4. 交付说明
Write-Step "同事侧需要做的唯一一步"
Write-Host @"

    把这个文件发给同事：
      $cerPath

    同事双击「安装包」若仍提示未知发布者，让他：
      1. 右键 .cer 文件 → 「安装证书」
      2. 选择「本地计算机」→ 下一步（需管理员）
      3. 「将所有证书放入下列存储」→ 「受信任的根证书颁发机构」
      4. 完成后重新运行安装包，提示消失

    管理员批量下发：在域策略里导入 .cer 即可全公司生效。

"@ -ForegroundColor Gray

Write-Host "签名完成：成功 $signed 个，失败 $failed 个`n" -ForegroundColor Cyan
if ($failed -gt 0) { exit 1 }
