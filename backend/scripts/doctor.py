# -*- coding: utf-8 -*-
"""ChemELN 自助诊断 — 一条一条查清楚「为什么进不去」，并给出人话结论。

用法（通常由项目根目录的 诊断.bat 调用）：
    python backend\\scripts\\doctor.py            只诊断，不改变任何东西
    python backend\\scripts\\doctor.py --start    诊断后顺手把服务启动起来
    python backend\\scripts\\doctor.py --log 30   多显示几行启动日志

输出编码：本脚本面向用户控制台，保持系统编码（中文 Windows = GBK/cp936），
只放宽不可编码字符。输出里刻意不使用 emoji / 勾叉等 GBK 码表外符号，
避免在重定向或隐藏窗口场景下抛 UnicodeEncodeError 让进程直接退出。
"""
import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time

# 输出编码守卫：不改编码，只放宽不可编码字符
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
VENV_DIR = os.path.join(BACKEND, "venv")
VENV_PY = os.path.join(VENV_DIR, "Scripts", "python.exe")
VENV_PYW = os.path.join(VENV_DIR, "Scripts", "pythonw.exe")
MAIN_PY = os.path.join(BACKEND, "main.py")
DB = os.path.join(BACKEND, "data", "chemeln.db")
ATTACH = os.path.join(BACKEND, "data", "attachments")
LAUNCH_PY = os.path.join(BACKEND, "scripts", "launch.py")
LAUNCH_LOG = os.path.join(BACKEND, "data", "launch.log")
START_BAT = os.path.join(ROOT, "start_windows.bat")
DESKTOP_BAT_NAME = "打开合迹ChemELN.bat"

PORT = 8765
PROBLEMS = []   # 会导致「进不去」的硬问题
NOTES = []      # 提醒，不致命


def ok(msg):
    print(f"  [OK] {msg}")


def bad(msg):
    print(f"  [!!] {msg}")
    PROBLEMS.append(msg)


def note(msg):
    print(f"  [--] {msg}")
    NOTES.append(msg)


def section(title):
    print()
    print("-" * 62)
    print(title)
    print("-" * 62)


def desktop_dir() -> str:
    """真实桌面目录（可能被 OneDrive 重定向）。"""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
        if buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def port_listening(port=PORT, host="127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


# ---------------------------------------------------------------- 各项检查
def check_files():
    section("1. 程序文件")
    for label, path in [("主程序 main.py", MAIN_PY),
                        ("虚拟环境 python.exe", VENV_PY),
                        ("启动器 launch.py", LAUNCH_PY),
                        ("一键启动 start_windows.bat", START_BAT),
                        ("重启入口 重启服务.bat", os.path.join(ROOT, "重启服务.bat"))]:
        if os.path.exists(path):
            ok(f"{label} 存在")
        else:
            bad(f"{label} 缺失: {path}")
    if os.path.isdir(VENV_DIR) and not os.path.exists(VENV_PY):
        bad("虚拟环境目录存在但不完整，建议重新运行 install.bat")


def check_deps():
    section("2. 运行依赖")
    if not os.path.exists(VENV_PY):
        bad("虚拟环境缺失，无法检查依赖")
        return
    code = (
        "import importlib,sys\n"
        "miss=[]\n"
        "for n in ['fastapi','uvicorn','multipart','aiofiles','openpyxl',\n"
        "          'rdkit','docx','xhtml2pdf','bs4','httpx','pyhanko','PIL']:\n"
        "    try: importlib.import_module(n)\n"
        "    except Exception: miss.append(n)\n"
        "print(','.join(miss))\n")
    try:
        r = subprocess.run([VENV_PY, "-c", code], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           cwd=BACKEND, timeout=180)
        miss = [x for x in (r.stdout or "").strip().split(",") if x]
        if miss:
            bad(f"缺少依赖: {', '.join(miss)}（运行 install.bat 可自动补齐）")
        else:
            ok("依赖完整（12 个关键包全部可导入）")
    except Exception as e:
        bad(f"依赖检查失败: {type(e).__name__}: {e}")

    # PDF 导出链路必须真跑一次。
    # 只 import xhtml2pdf 是查不出问题的：它的包 __init__ 不加载渲染器，
    # 真正缺 pyhanko（xhtml2pdf>=0.2.17 的必需依赖）时 import 依然成功，
    # 界面上显示"依赖完整"，直到点导出 PDF 才 500。
    pdf_code = (
        "import io\n"
        "from xhtml2pdf import pisa\n"
        "b=io.BytesIO()\n"
        "pisa.CreatePDF('<h1>ok</h1>',dest=b,encoding='utf-8')\n"
        "print(len(b.getvalue()))\n")
    try:
        r2 = subprocess.run([VENV_PY, "-c", pdf_code], capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            cwd=BACKEND, timeout=180)
        out = (r2.stdout or "").strip().splitlines()
        n = int(out[-1]) if out and out[-1].isdigit() else 0
        if r2.returncode != 0 or n <= 0:
            tail = (r2.stderr or "").strip().splitlines()
            why = tail[-1] if tail else "渲染未产出内容"
            bad(f"PDF 导出不可用（导出 PDF 会失败）: {why}")
            note("运行 install.bat 可自动补齐 pdf 渲染依赖")
        else:
            ok(f"PDF 导出可用（渲染自检通过，{n} 字节）")
    except Exception as e:
        bad(f"PDF 渲染自检失败: {type(e).__name__}: {e}")

    # 导出字体：统一 Times New Roman + 宋体。
    # 字体文件在 C:\Windows\Fonts 下，缺失时会自动降级（仍能导出，但字形不同），
    # 降级是静默的，用户只会"觉得字不对"，所以这里要说出来。
    font_code = (
        "import json\n"
        "from utils import export_formats as exf\n"
        "print(json.dumps(exf.font_status(), ensure_ascii=False))\n")
    try:
        r3 = subprocess.run([VENV_PY, "-c", font_code], capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            cwd=BACKEND, timeout=300)
        lines = [x for x in (r3.stdout or "").strip().splitlines() if x.strip()]
        st = json.loads(lines[-1]) if lines else {}
        latin, cjk = st.get("latin"), st.get("cjk")
        if st.get("error"):
            note(f"导出字体自检未完成: {st['error']}")
        elif latin == "Times New Roman" and cjk == "SimSun":
            ok("导出字体: 西文 Times New Roman + 中文 宋体")
        else:
            note(f"导出字体已降级（缺字体文件）: 西文={latin} 中文={cjk} —— "
                 "导出仍可用，但字形与标准排版不同")
        emb = st.get("embedded") or []
        if any("TimesNewRoman" in e or "SimSun" in e for e in emb):
            ok(f"字体已内嵌进 PDF（{', '.join(emb)}），换台电脑打开也不会变样")
    except Exception as e:
        note(f"导出字体检查跳过: {type(e).__name__}: {e}")


def check_data():
    section("3. 数据（最重要）")
    if not os.path.exists(DB):
        bad(f"数据库不存在: {DB}")
        return
    size = os.path.getsize(DB) / 1024
    ok(f"数据库存在，{size:,.0f} KB")
    try:
        c = sqlite3.connect(DB)
        counts = {}
        for t in ("experiments", "compounds", "templates", "tags"):
            counts[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
        c.close()
        ok(f"数据完整性检查: {integrity}")
        ok("实验 %d 条 / 化合物 %d 个 / 模板 %d 个 / 标签 %d 个"
           % (counts["experiments"], counts["compounds"],
              counts["templates"], counts["tags"]))
    except Exception as e:
        bad(f"数据库无法读取（可能损坏）: {type(e).__name__}: {e}")
    if os.path.isdir(ATTACH):
        n = sum(len(f) for _r, _d, f in os.walk(ATTACH))
        ok(f"附件目录正常，共 {n} 个文件")
    else:
        note("附件目录不存在（没有附件时可忽略）")

    auto_dir = os.path.join(BACKEND, "data", "backups", "auto")
    if os.path.isdir(auto_dir):
        zips = [f for f in os.listdir(auto_dir) if f.endswith(".zip")]
        if zips:
            newest = max(zips, key=lambda f: os.path.getmtime(os.path.join(auto_dir, f)))
            t = time.strftime("%Y-%m-%d %H:%M", time.localtime(
                os.path.getmtime(os.path.join(auto_dir, newest))))
            ok(f"自动备份可用，最近一份: {newest}（{t}）")
        else:
            note("还没有自动备份文件，服务运行满一个周期后会自动生成")
    else:
        note("尚未建立自动备份目录（首次启动服务后会自动创建）")


def read_health(port=PORT, timeout=3.0):
    """读取运行中服务的 /api/health；失败返回 None。"""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health",
                                    timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def local_code_fingerprint() -> str:
    try:
        sys.path.insert(0, BACKEND)
        from utils.code_fingerprint import compute
        return compute()
    except Exception:
        return ""


def check_service():
    """返回服务是否在运行。'服务没在运行'是状态而非故障，故不计入 PROBLEMS。"""
    section("4. 服务运行状态")
    if port_listening():
        ok(f"端口 {PORT} 正在监听 —— 服务已运行")
        ok(f"请在浏览器访问  http://localhost:{PORT}")

        # 「服务在跑」不等于「跑的是当前代码」：后端是常驻进程，
        # 改完代码如果不重启，页面/导出会一直是老样子（最容易被误判成没修好）。
        info = read_health()
        local_fp = local_code_fingerprint()
        if info is None:
            note("读不到 /api/health —— 端口被别的程序占用，或服务卡住了")
        else:
            ver = info.get("version", "?")
            remote_fp = info.get("code_fingerprint")
            if not remote_fp:
                bad(f"运行中的服务是旧版本代码（version={ver}，无代码指纹）—— "
                    "重新双击桌面入口会自动换新；或双击 重启服务.bat")
            elif local_fp and remote_fp != local_fp:
                bad(f"运行中的服务与磁盘上的代码不一致（运行 {remote_fp} / "
                    f"本地 {local_fp}）—— 重新双击桌面入口会自动换新；"
                    "或双击 重启服务.bat")
            else:
                ok(f"运行的是当前代码（version={ver}，指纹 {remote_fp}）")
        return True

    print(f"  [--] 服务当前未运行（端口 {PORT} 没有监听）")
    # 找出是否残留进程
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq pythonw.exe",
                            "/FO", "CSV", "/NH"], capture_output=True)
        txt = r.stdout.decode("gbk", errors="replace").strip()
        if txt and "pythonw" in txt:
            print("  [--] 检测到残留 pythonw.exe 进程（可能是上一次没退干净）:")
            for line in txt.splitlines():
                print("        " + line)
    except Exception:
        pass
    return False


def check_entries():
    section("5. 启动入口（双击能不能起得来）")
    target = os.path.join(desktop_dir(), DESKTOP_BAT_NAME)
    if os.path.exists(target):
        raw = open(target, "rb").read()
        non_ascii = any(b > 127 for b in raw)
        bare_lf = raw.count(b"\n") - raw.count(b"\r\n")
        if non_ascii:
            bad(f"桌面入口 {DESKTOP_BAT_NAME} 含非 ASCII 字符 —— cmd 下会乱码，"
                "双击后窗口一闪就没反应（运行 install.bat 可自动重建）")
        elif bare_lf > 0:
            bad(f"桌面入口 {DESKTOP_BAT_NAME} 是 LF 换行（应为 CRLF）—— "
                "cmd 可能解析失败（运行 install.bat 可自动重建）")
        else:
            ok(f"桌面入口 {DESKTOP_BAT_NAME} 正常（纯 ASCII / CRLF）")
    else:
        note(f"桌面 .bat 兜底入口 {DESKTOP_BAT_NAME} 不存在（用桌面快捷方式即可，非必需）")

    lnk = os.path.join(desktop_dir(), "合迹ChemELN.lnk")
    if os.path.exists(lnk):
        ok("桌面快捷方式「合迹ChemELN.lnk」存在")
    else:
        note("桌面快捷方式不存在（运行 install.bat 可重建）")

    try:
        startup = os.path.join(os.environ.get("APPDATA", ""),
                               r"Microsoft\Windows\Start Menu\Programs\Startup")
        auto = os.path.join(startup, "ChemELN-Backend.vbs")
        if os.path.exists(auto):
            ok("开机自启项存在（登录后会自动启动服务）")
        else:
            note("开机自启项不存在（运行 install.bat 可添加）")
    except Exception:
        pass


def check_log(max_lines=12):
    section("6. 最近启动日志")
    if not os.path.exists(LAUNCH_LOG):
        note("还没有启动日志（服务从未被启动过）")
        return
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(LAUNCH_LOG)))
    print(f"  文件: {LAUNCH_LOG}")
    print(f"  最后写入: {t}")
    print()
    try:
        lines = open(LAUNCH_LOG, encoding="utf-8", errors="replace").read().splitlines()
        for line in lines[-max_lines:]:
            print("    | " + line)
    except Exception as e:
        note(f"日志读取失败: {type(e).__name__}: {e}")


def try_start() -> bool:
    section("7. 尝试启动服务")
    if port_listening():
        ok("服务已在运行，无需启动")
        return True
    if not (os.path.exists(VENV_PY) and os.path.exists(LAUNCH_PY)):
        bad("缺少运行环境或启动器，无法自动启动（请先运行 install.bat）")
        return False
    print("  正在启动，请稍候（首次约 3-10 秒）...")
    try:
        rc = subprocess.call([VENV_PY, LAUNCH_PY, "--no-browser"], cwd=BACKEND)
    except Exception as e:
        bad(f"启动命令执行失败: {type(e).__name__}: {e}")
        return False
    if port_listening():
        ok(f"服务已启动 —— 浏览器访问  http://localhost:{PORT}")
        return True
    bad(f"启动未成功（返回码 {rc}），请查看上面的启动日志找原因")
    return False


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", action="store_true", help="诊断后顺手启动服务")
    ap.add_argument("--log", type=int, default=12, help="显示最近多少行日志")
    args = ap.parse_args()

    print("=" * 62)
    print("   合迹 ChemELN  自助诊断")
    print("=" * 62)

    check_files()
    check_deps()
    check_data()
    running = check_service()
    check_entries()
    check_log(args.log)

    if args.start and not running:
        running = try_start()

    section("诊断结论")
    if PROBLEMS:
        print("  发现 %d 个需要处理的问题：" % len(PROBLEMS))
        for p in PROBLEMS:
            print("    - " + p)
        print()
        print("  建议：双击项目目录里的 install.bat 自动修复环境与启动入口，")
        print("        修复后双击桌面图标「合迹ChemELN」即可使用。")
    elif running:
        print("  一切正常，服务正在运行。")
        print(f"  在浏览器访问  http://localhost:{PORT}")
    else:
        print("  环境和数据都正常，只是服务当前没在运行。")
        print("  双击桌面图标「合迹ChemELN」或项目目录里的 重启服务.bat 即可启动")
        print("  （也可以重跑本诊断加 --start）。")
    if NOTES:
        print()
        print("  另外 %d 条提醒（不影响使用）：" % len(NOTES))
        for n in NOTES:
            print("    - " + n)
    print()
    print("=" * 62)
    print("  提示：数据都在 backend\\data 里，任何情况下都不要删除该目录。")
    print("=" * 62)
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    sys.exit(main())
