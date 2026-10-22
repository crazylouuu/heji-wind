# -*- coding: utf-8 -*-
"""ChemELN 环境安装 — 检测/建虚拟环境/装依赖/初始化数据库/建快捷方式/启动。

设计说明：
    安装流程复杂（探测、重试、回退镜像），放在 .bat 里极易因引号与管道问题
    整批终止且不留日志。因此全部逻辑集中在本脚本，install.bat 只负责
    「找到系统 Python 并把控制权交过来」。

用法（由 install.bat 调用，或手动）：
    python backend\\scripts\\setup_env.py
    python backend\\scripts\\setup_env.py --check-only   只体检，不改动
    python backend\\scripts\\setup_env.py --no-start     装完不启动
    python backend\\scripts\\setup_env.py --no-shortcuts 不创建快捷方式/自启
"""
import argparse
import os
import subprocess
import sys
import time

# 输出编码守卫：本脚本输出给用户控制台，保持系统编码（Windows 通常 GBK/cp936），
# 只放宽不可编码字符。若强行改用 UTF-8，经 cmd 的 GBK 控制台会显示成乱码。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
VENV_DIR = os.path.join(BACKEND, "venv")
VENV_PY = os.path.join(VENV_DIR, "Scripts", "python.exe")
REQ = os.path.join(BACKEND, "requirements.txt")
SHORTCUTS_VBS = os.path.join(ROOT, "setup_shortcuts.vbs")
START_BAT = os.path.join(ROOT, "start_windows.bat")
LAUNCH_PY = os.path.join(BACKEND, "scripts", "launch.py")
LOG_PATH = os.path.join(BACKEND, "data", "install.log")

DESKTOP_BAT_NAME = "打开合迹ChemELN.bat"
DESKTOP_LNK_NAME = "合迹ChemELN.lnk"
ICON_ICO = os.path.join(ROOT, "frontend", "img", "logo.ico")
ICON_PNG = os.path.join(ROOT, "frontend", "img", "logo.png")

# requirements.txt 里的包 → import 名
DEPS = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("python-multipart", "multipart"),
    ("aiofiles", "aiofiles"),
    ("openpyxl", "openpyxl"),
    ("rdkit", "rdkit"),
    ("python-docx", "docx"),
    ("xhtml2pdf", "xhtml2pdf"),
    ("beautifulsoup4", "bs4"),
    ("httpx", "httpx"),
]
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

FAILS = []


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(cmd, **kw):
    """跑外部命令，回显实时输出，返回 returncode。"""
    kw.setdefault("cwd", BACKEND)
    try:
        return subprocess.call(cmd, **kw)
    except FileNotFoundError:
        return 127


def step(n, total, title):
    print()
    print(f"[{n}/{total}] {title}")


# ---------------------------------------------------------------- 各步骤
def check_python() -> bool:
    v = sys.version_info
    log(f"Python {v.major}.{v.minor}.{v.micro} @ {sys.executable}")
    if v < (3, 9):
        log("错误: 需要 Python 3.9 或更高版本")
        FAILS.append("Python 版本过低")
        return False
    if "venv" in sys.executable.replace("\\", "/").split("/"):
        log("提示: 当前已在虚拟环境中运行")
    return True


def ensure_venv() -> bool:
    if os.path.exists(VENV_PY):
        log("虚拟环境已存在，跳过创建")
        return True
    log("首次安装，正在创建虚拟环境（约 10-30 秒）...")
    rc = run([sys.executable, "-m", "venv", VENV_DIR])
    if rc != 0 or not os.path.exists(VENV_PY):
        log("错误: 虚拟环境创建失败，请确认 Python 安装完整（包含 venv 模块）")
        FAILS.append("创建虚拟环境失败")
        return False
    log("虚拟环境创建完成")
    return True


def missing_deps() -> list:
    """返回缺失的 import 名列表。"""
    if not os.path.exists(VENV_PY):
        return [imp for _pkg, imp in DEPS]
    code = ("import importlib, sys\n"
            "missing = []\n"
            "for name in sys.argv[1:]:\n"
            "    try:\n"
            "        importlib.import_module(name)\n"
            "    except Exception:\n"
            "        missing.append(name)\n"
            "print(','.join(missing))\n")
    try:
        out = subprocess.run([VENV_PY, "-c", code] + [imp for _p, imp in DEPS],
                             capture_output=True, text=True, cwd=BACKEND,
                             encoding="utf-8", errors="replace", timeout=180)
        txt = (out.stdout or "").strip()
        return [x for x in txt.split(",") if x]
    except Exception as e:
        log(f"依赖体检异常（按全部缺失处理）: {type(e).__name__}: {e}")
        return [imp for _p, imp in DEPS]


def ensure_deps(check_only=False) -> bool:
    need = missing_deps()
    if not need:
        log("依赖已就绪，跳过安装")
        return True
    log(f"缺失依赖: {', '.join(need)}")
    if check_only:
        FAILS.append(f"依赖缺失: {', '.join(need)}")
        return False
    if not os.path.exists(REQ):
        log(f"错误: 未找到 {REQ}")
        FAILS.append("requirements.txt 缺失")
        return False

    log("正在安装依赖，首次约 2-5 分钟，请耐心等待...")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    rc = run([VENV_PY, "-m", "pip", "install", "--upgrade", "pip", "-q"],
             env=env)
    rc = run([VENV_PY, "-m", "pip", "install", "-r", REQ, "-i", MIRROR], env=env)
    if rc != 0:
        log("提示: 镜像源失败，改用官方源重试...")
        rc = run([VENV_PY, "-m", "pip", "install", "-r", REQ], env=env)

    still = missing_deps()
    if still:
        log(f"错误: 依赖安装失败，仍缺失: {', '.join(still)}")
        log("请检查网络连接后重新运行 install.bat")
        FAILS.append(f"依赖安装失败: {', '.join(still)}")
        return False
    log("依赖安装完成")
    return True


def init_database() -> bool:
    code = ("import sys; sys.path.insert(0, r'%s'); "
            "import database; database.init_db(); print('OK')" % BACKEND)
    try:
        out = subprocess.run([VENV_PY, "-c", code], capture_output=True,
                             text=True, cwd=BACKEND, encoding="utf-8",
                             errors="replace", timeout=300)
        if (out.stdout or "").strip().endswith("OK"):
            log("数据库初始化完成")
            return True
        log(f"数据库初始化异常: {(out.stderr or '').strip()[:300]}")
    except Exception as e:
        log(f"数据库初始化异常: {type(e).__name__}: {e}")
    FAILS.append("数据库初始化失败")
    return False


def desktop_dir() -> str:
    """真实桌面目录（可能被 OneDrive 重定向，故走系统 API 而非 ~/Desktop）。"""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY = 0x0010
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
        if buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def desktop_launcher_bytes() -> bytes:
    """桌面入口内容 —— 纯 ASCII + CRLF 的转发薄壳。

    ⛔ 为什么要纯 ASCII：
        cmd.exe 用 OEM 代码页（中文系统 936/GBK）解码 .bat。若文件以 UTF-8
        保存且含中文，中文会解码成乱码，乱码字节破坏引号配对，cmd 在毫秒级
        报一堆「不是内部或外部命令」后退出 —— 用户看到的就是「窗口一闪，
        什么都没发生」。纯 ASCII 在 ASCII/UTF-8/GBK 下字节完全一致，从根上
        免疫；LF-only 换行同样会让 cmd 解析块失败，所以统一 CRLF。

    桌面副本曾因编码腐化导致「双击打不开」，故由安装流程统一生成覆盖。
    """
    lines = [
        "@echo off",
        "REM ============================================================",
        "REM  ChemELN desktop launcher -- thin shell, deliberately no logic.",
        "REM  Start / wait-for-ready / open-browser logic lives in:",
        f"REM    {START_BAT}",
        "REM",
        "REM  Pure ASCII on purpose: a UTF-8 .bat containing Chinese text is",
        "REM  mis-decoded by cmd (OEM cp936), which breaks quoting and makes",
        "REM  the script abort within milliseconds.",
        "REM  If the project folder moves, re-run install.bat to regenerate.",
        "REM ============================================================",
        "chcp 936 >nul 2>&1",
        f'call "{START_BAT}"',
        "exit /b %errorlevel%",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def make_desktop_launcher() -> bool:
    data = desktop_launcher_bytes()
    if any(b > 127 for b in data):
        log("错误: 桌面入口生成内容含非 ASCII 字符，已中止")
        return False
    try:
        target = os.path.join(desktop_dir(), DESKTOP_BAT_NAME)
        with open(target, "wb") as f:
            f.write(data)
        log(f"已生成/刷新桌面启动入口: {DESKTOP_BAT_NAME}（纯 ASCII，CRLF）")
        return True
    except Exception as e:
        log(f"桌面启动入口生成失败: {type(e).__name__}: {e}")
        return False


def check_desktop_launcher() -> list:
    """体检桌面入口，返回「需要修复」的问题列表（空列表 = 正常）。

    入口有两种形态，任一可用即可：
      1) 合迹ChemELN.lnk        安装流程用 setup_shortcuts.vbs 创建，带品牌图标
      2) 打开合迹ChemELN.bat    纯 ASCII 兜底（快捷方式创建失败时才生成）
    """
    problems = []
    lnk = os.path.join(desktop_dir(), DESKTOP_LNK_NAME)
    bat = os.path.join(desktop_dir(), DESKTOP_BAT_NAME)

    if os.path.exists(lnk):
        return problems          # 带图标快捷方式在，就是健康状态
    if not os.path.exists(bat):
        problems.append("桌面启动入口缺失（既没有「合迹ChemELN」快捷方式，"
                        "也没有 打开合迹ChemELN.bat）—— 运行 install.bat 可修复")
        return problems

    try:
        with open(bat, "rb") as f:
            raw = f.read()
    except Exception as e:
        problems.append(f"桌面启动入口无法读取: {type(e).__name__}: {e}")
        return problems
    if any(b > 127 for b in raw):
        problems.append("桌面启动入口含非 ASCII 字符，cmd 下会乱码导致双击无反应"
                        "（运行 install.bat 可自动重建）")
    if raw.count(b"\n") - raw.count(b"\r\n") > 0:
        problems.append("桌面启动入口使用了 LF 换行（应为 CRLF），"
                        "可能导致 cmd 解析异常（运行 install.bat 可自动重建）")
    return problems


def desktop_entry_notes() -> list:
    """提示性信息（不计入体检失败），例如两个入口并存。"""
    notes = []
    lnk = os.path.join(desktop_dir(), DESKTOP_LNK_NAME)
    bat = os.path.join(desktop_dir(), DESKTOP_BAT_NAME)
    if os.path.exists(lnk) and os.path.exists(bat):
        notes.append(f"桌面同时存在「{DESKTOP_LNK_NAME}」（带图标）与「{DESKTOP_BAT_NAME}」，"
                     "两者都能启动；一般保留带图标的快捷方式即可，旧的 .bat 可自行删除"
                     "（本工具不会自动删除桌面文件）")
    return notes


def check_icons() -> list:
    """体检品牌图标资源（缺失时快捷方式与浏览器标签会退回默认图标）。"""
    problems = []
    for path, label in ((ICON_ICO, "frontend/img/logo.ico — 快捷方式/标签页图标"),
                        (ICON_PNG, "frontend/img/logo.png — 页面 logo")):
        if not os.path.exists(path):
            problems.append(f"品牌图标缺失: {label}"
                            "（可运行 backend\\scripts\\make_icon.py 重新生成）")
    return problems


def make_shortcuts() -> bool:
    if not os.path.exists(SHORTCUTS_VBS):
        log("未找到 setup_shortcuts.vbs，跳过快捷方式")
        return False
    rc = run(["cscript", "//nologo", SHORTCUTS_VBS, "install"], cwd=ROOT)
    if rc == 0:
        icon_note = "（图标: frontend\\img\\logo.ico）" if os.path.exists(ICON_ICO) else ""
        log(f"已创建桌面快捷方式 + 开机自动启动{icon_note}")
        return True
    log("提示: 快捷方式创建失败，可手动双击 start_windows.bat 启动")
    return False


def start_service() -> bool:
    if not os.path.exists(LAUNCH_PY):
        log("未找到 launch.py，跳过启动")
        return False
    rc = run([VENV_PY, LAUNCH_PY, "--no-browser"], cwd=BACKEND)
    return rc == 0


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="只体检不改动")
    ap.add_argument("--no-start", action="store_true", help="装完不启动服务")
    ap.add_argument("--no-shortcuts", action="store_true", help="不建快捷方式")
    args = ap.parse_args()

    print("=" * 56)
    print("   合迹 ChemELN  安装程序")
    print("=" * 56)
    print("   数据保存在 backend\\data，卸载不会删除数据")
    print("=" * 56)

    total = 5
    step(1, total, "检测 Python 环境")
    if not check_python():
        return 1

    step(2, total, "准备虚拟环境")
    if not args.check_only and not ensure_venv():
        return 1
    if args.check_only and not os.path.exists(VENV_PY):
        FAILS.append("虚拟环境未创建")

    step(3, total, "检查并安装依赖")
    if not ensure_deps(check_only=args.check_only):
        return 1

    if args.check_only:
        print()
        print("-" * 56)
        print("附加体检: 启动入口与品牌图标")
        entry_problems = check_desktop_launcher() + check_icons()
        if entry_problems:
            for p in entry_problems:
                print(f"  - {p}")
        else:
            print("  - 桌面启动入口正常（带图标快捷方式或纯 ASCII 兜底 .bat）")
            print("  - 品牌图标齐全（logo.ico / logo.png）")
        for n in desktop_entry_notes():
            print(f"  提示: {n}")
        FAILS.extend(entry_problems)
        print("-" * 56)
        if FAILS:
            print("体检发现问题：")
            for f in FAILS:
                print(f"  - {f}")
            return 1
        print("体检通过：环境完整，可直接启动")
        return 0

    step(4, total, "初始化数据库")
    init_database()

    print()
    step(5, total, "创建快捷方式与开机自启")
    if not args.no_shortcuts:
        # 优先带品牌图标的快捷方式；它建不出来才退回纯 ASCII 的 .bat 兜底。
        if not make_shortcuts():
            log("改用纯 ASCII 的桌面 .bat 作为兜底入口")
            make_desktop_launcher()
    else:
        print("已跳过")

    if not args.no_start:
        print()
        print("正在启动服务...")
        start_service()

    print()
    print("=" * 56)
    if FAILS:
        print("   安装完成，但有需要注意的问题：")
        for f in FAILS:
            print(f"     - {f}")
        print("=" * 56)
        return 1
    print("   安装完成！")
    print("=" * 56)
    print("   今后双击桌面的「合迹ChemELN」图标即可使用")
    print("   浏览器访问 http://localhost:8765")
    print("   如需卸载：运行 uninstall.bat（不会删除数据）")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
