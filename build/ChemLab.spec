# -*- mode: python ; coding: utf-8 -*-
"""ChemLab Python 后端 —— PyInstaller onedir 打包配置（P6）。

为什么是 onedir 而不是 onefile
--------------------------------
- onefile 每次启动都要把依赖解压到临时目录，**杀软更容易误报**（R1 风险）；
  onedir 是固定目录的文件，杀软的白名单/签名策略更稳（沿用合迹已验证的结论）。
- onedir 启动快得多 —— 主壳拉起后端时这一点很关键。
- 缺点是目录大（RDKit 占大头），但随 NSIS 安装包分发，用户无感。

为什么打包产物叫 ChemLabBackend
--------------------------------
它是**主壳的 sidecar**，不是给用户单独双击的应用：
- 由 Tauri 主壳 spawn，注入 CHEMLAB_TOKEN 与 --port
- 端口占用时静默退出（不弹浏览器）—— 由主壳决定怎么复用已有实例
- 日志写到 %APPDATA%\\ChemLab\\logs\\backend.log（打包版没有 stdout）

资源说明
--------
- ``frontend-chemeln``（合迹前端静态资源）打进包里 → _MEIPASS/frontend
  config.frontend_dir() 优先找 "frontend"，正好命中
- RDKit 必须 collect_all：大量子模块 + 数据文件（周期表、SMARTS 等）
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# RDKit：子模块 + 数据文件 + 二进制，全部收
rdkit_datas, rdkit_binaries, rdkit_hiddenimports = collect_all("rdkit")

hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("multipart")
hiddenimports += collect_submodules("aiofiles")
hiddenimports += rdkit_hiddenimports

datas = [
    # 合迹前端静态资源（iframe / 子 webview 加载的就是它）
    ("../frontend-chemeln", "frontend"),
    # 工具箱前端（Vue SPA）—— 由后端托管在 /toolbox 下，
    # 供「不用 Tauri 壳」的浏览器模式使用。
    # 目标目录名必须是 frontend-toolbox，与 config.toolbox_dir() 的
    # 第一个候选（<资源根>/frontend-toolbox）对应。
    # 源目录由 build.ps1 在 PyInstaller 之前从 dist/ 复制而来。
    ("../backend/frontend-toolbox", "frontend-toolbox"),
    # SOP 资源（18 份 Markdown + 配图，84K）—— 由 /api/sop/* 提供，
    # 目标路径与 config.sops_dir()（<资源根>/assets/sops）对应
    ("../assets/sops", "assets/sops"),
] + rdkit_datas

binaries = rdkit_binaries

a = Analysis(
    ["../backend/main.py"],
    pathex=["../backend"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc_data", "test"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,             # onedir：二进制交给 COLLECT
    name="ChemLabBackend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                         # 不做 UPX 压缩（压缩壳更容易被杀软误报）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                     # 无控制台窗口；日志走文件
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="../src-tauri/icons/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ChemLabBackend",
)
