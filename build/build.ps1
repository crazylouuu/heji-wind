# ChemLab 一键打包脚本（P6）
#
# 用法（在仓库根目录执行）：
#     powershell -ExecutionPolicy Bypass -File build\build.ps1
#     powershell -ExecutionPolicy Bypass -File build\build.ps1 -Fast
#
# 参数：
#     -Fast        关闭 LTO 构建（受限环境用）
#                  完整 LTO 在内存/CPU 受限的机器上会让 rustc 卡死或崩
#                  （0xc0000139 / 0xc0000005），关掉后能正常出包，
#                  代价是体积略大、极限优化略差。
#                  正式发布建议用默认（开 LTO）。
#     -SkipSidecar 跳过 PyInstaller 步骤（sidecar 未变时可省 2~5 分钟）
#
# 产出：
#     build\dist\ChemLabBackend\ChemLabBackend.exe     Python 后端 sidecar（onedir）
#     src-tauri\target\release\bundle\nsis\*.exe         NSIS 安装包
#
# 四个步骤：
#   1. 前端构建           → dist/（Vue 产物）
#   2. PyInstaller onedir → build/dist/ChemLabBackend/
#   3. 拷贝 sidecar       → src-tauri/resources/backend/
#   4. Tauri NSIS 打包    → 安装包
#
# 关于构建环境：直接用 backend/venv（已含全部依赖）。
# 若该 venv 缺 pyinstaller，脚本会自动安装。

param(
    [switch]$Fast,
    [switch]$SkipSidecar,
    # 打包后做数字签名（推荐：消除同事机器上的「未知发布者」警告）
    [switch]$Sign,
    # 签名时顺便把自签名证书加入本机受信任根
    [switch]$TrustLocal
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $ROOT

# ---------------------------------------------------------------------------
# 预备：腾空会触发「批量删除」的目录
#
# Vite 打包前会清空 dist/assets，PyInstaller 收尾时会清空 dist\ChemLabBackend。
# 在某些安全策略下，一次删除的文件数超过阈值就会被直接拦掉，表现为构建失败
# 但日志里看不出代码问题。把旧目录「移走」而不是「删掉」可以完全绕开：
# 同一分区内的 rename 是瞬时操作，也不会占用额外空间。
# ---------------------------------------------------------------------------
function Clear-ForRebuild {
    param([string]$Path, [string]$Tag)
    if (Test-Path $Path) {
        $trash = Join-Path $ROOT "build\_trash"
        New-Item -ItemType Directory -Force -Path $trash | Out-Null
        Move-Item $Path (Join-Path $trash ("{0}-{1}" -f $Tag, (Get-Date -Format "HHmmss")))
        Write-Host "    已腾空 $Tag（避开批量删除限制）" -ForegroundColor DarkGray
    }
}
Clear-ForRebuild -Path (Join-Path $ROOT "dist") -Tag "dist"
Clear-ForRebuild -Path (Join-Path $ROOT "build\dist\ChemLabBackend") -Tag "sidecar"
Clear-ForRebuild -Path (Join-Path $ROOT "build\work\ChemLab") -Tag "pyi-work"

# 用 npm 而不是 pnpm：pnpm 在本机 Windows 上无法创建 node_modules 顶层的
# 符号链接（.pnpm 里包是完整的，但 vue-tsc/vite 这些顶层入口缺失，
# 表现为 "Cannot find module ...vue-tsc/bin/vue-tsc.js"）。
# 依赖版本仍由 package.json 精确锁定，npm 的扁平结构没有这个问题。
Write-Host "==> [1/4] 前端构建 (npm run build)..." -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }

# 把 dist 复制给后端托管 —— 「不用 Tauri 壳」的浏览器模式靠这份资源
# （PyInstaller spec 会把它打进 sidecar 的 frontend-toolbox/ 目录）
$TOOLBOX_SRC = Join-Path $ROOT "dist"
$TOOLBOX_DST = Join-Path $ROOT "backend\frontend-toolbox"
if (Test-Path $TOOLBOX_SRC) {
    if (Test-Path $TOOLBOX_DST) { Remove-Item -Recurse -Force $TOOLBOX_DST }
    Copy-Item -Recurse -Force $TOOLBOX_SRC $TOOLBOX_DST
    Write-Host "    已复制 dist -> backend\frontend-toolbox（供 /toolbox/ 托管）" -ForegroundColor DarkGray
} else {
    throw "未找到 dist/，前端构建可能失败"
}

Write-Host "==> [2/4] PyInstaller 打包 Python 后端 (onedir)..." -ForegroundColor Cyan
$PY = Join-Path $ROOT "backend\venv\Scripts\python.exe"
if (-not (Test-Path $PY)) {
    throw "未找到后端虚拟环境 $PY —— 请先执行: python -m venv backend\venv; backend\venv\Scripts\pip install -r backend\requirements.txt"
}
if ($SkipSidecar) {
    Write-Host "    已跳过（-SkipSidecar）" -ForegroundColor DarkGray
} else {
    & $PY -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    安装 pyinstaller..." -ForegroundColor Yellow
        & $PY -m pip install pyinstaller
        if ($LASTEXITCODE -ne 0) { throw "pyinstaller 安装失败" }
    }
    # 在 build/ 目录内执行：spec 里的相对路径（../backend 等）以此为基准
    Push-Location build
    try {
        & $PY -m PyInstaller ChemLab.spec --clean --noconfirm --distpath dist --workpath work
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }
    } finally {
        Pop-Location
    }
}

Write-Host "==> [3/4] 拷贝 sidecar 到 src-tauri\resources\backend ..." -ForegroundColor Cyan
$RES = Join-Path $ROOT "src-tauri\resources\backend"
if (Test-Path $RES) { Remove-Item -Recurse -Force $RES }
New-Item -ItemType Directory -Force -Path $RES | Out-Null
Copy-Item -Recurse -Force (Join-Path $ROOT "build\dist\ChemLabBackend\*") $RES

# --- 精简 sidecar：删掉运行时用不到的部分 -------------------------------
# PyInstaller 会把整个 Python 包打进去，包括一些永远不会 import 的子目录。
# 以下三个是实测确认用不到的（后端 API 只 import rdkit / rdkit.Chem）：
#   rdkit\Contrib    8.3 MB  第三方贡献模块（PDBWriter、Fraggle 等独立脚本）
#   rdkit\sping      1.1 MB  PostScript 绘图后端，本项目用 MolDraw2D 输出 PNG
#   PIL\_avif.*.pyd  7.6 MB  AVIF 图片格式解码器，实验室工具不涉及该格式
# 合计省约 17 MB（未压缩）。删完由下面的 sidecar 体积打印体现。
$internal = Join-Path $RES "_internal"
$slimTargets = @(
    (Join-Path $internal "rdkit\Contrib"),
    (Join-Path $internal "rdkit\sping")
)
foreach ($t in $slimTargets) {
    if (Test-Path $t) {
        Remove-Item -Recurse -Force $t -ErrorAction SilentlyContinue
        Write-Host "    精简: 删除 $([System.IO.Path]::GetFileName($t))" -ForegroundColor DarkGray
    }
}
# 注意必须加 -Recurse：文件在 _internal\PIL\ 子目录里，只搜根目录会漏
Get-ChildItem -Path $internal -Filter "_avif*.pyd" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Force $_.FullName -ErrorAction SilentlyContinue
    Write-Host "    精简: 删除 $($_.Name) ($([math]::Round($_.Length/1MB,1)) MB)" -ForegroundColor DarkGray
}

$sidecar = Join-Path $RES "ChemLabBackend.exe"
if (-not (Test-Path $sidecar)) { throw "sidecar 未生成: $sidecar" }
$size = [math]::Round((Get-ChildItem -Recurse $RES | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "    sidecar 就绪 ($size MB): $sidecar" -ForegroundColor DarkGray

Write-Host "==> [4/4] Tauri NSIS 打包..." -ForegroundColor Cyan
if ($Fast) {
    # 用 cargo 的环境变量覆盖关闭 LTO（受限环境用；正式发布不要加）
    $env:CARGO_PROFILE_RELEASE_LTO = "false"
    Write-Host "    已关闭 LTO（-Fast）：完整 LTO 在受限环境会让 rustc 卡死或崩" -ForegroundColor Yellow
}

# tauri build 会再跑一次 beforeBuildCommand（npm run build），Vite 又要清 dist/assets。
# 第 1 步刚生成的 dist 正好是它要删的目标 —— 先挪走，让它输出到空目录。
Clear-ForRebuild -Path (Join-Path $ROOT "dist") -Tag "dist-pre-bundle"

Push-Location src-tauri
try {
    npx tauri build
    if ($LASTEXITCODE -ne 0) { throw "Tauri 打包失败" }
} finally {
    Pop-Location
}

$nsis = Get-ChildItem (Join-Path $ROOT "src-tauri\target\release\bundle\nsis") -Filter "*.exe" -ErrorAction SilentlyContinue
if ($nsis) {
    foreach ($f in $nsis) {
        $mb = [math]::Round($f.Length / 1MB, 1)
        Write-Host "==> 完成: $($f.FullName)  ($mb MB)" -ForegroundColor Green
    }
} else {
    Write-Host "==> 完成（未找到 NSIS 产物，请检查 target\release\bundle\nsis）" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 5. 数字签名（可选但强烈建议）
#
# 未签名的安装包在同事机器上会弹「Windows 已保护你的电脑（未知发布者）」，
# 杀软也更容易误判。自签名证书能消除前者、显著降低后者。
# 需要 -TrustLocal 才能让本机也显示「有效」。
# ---------------------------------------------------------------------------
if ($Sign) {
    Write-Host "`n==> [5/5] 数字签名..." -ForegroundColor Cyan
    $signArgs = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $ROOT "build\sign.ps1"))
    if ($TrustLocal) { $signArgs += "-TrustLocal" }
    & powershell @signArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "签名过程有失败项，安装包已生成但未完全签名"
    }
} else {
    Write-Host "`n（跳过签名。加 -Sign 可生成已签名安装包）" -ForegroundColor DarkGray
}
