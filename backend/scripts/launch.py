# -*- coding: utf-8 -*-
"""ChemELN 启动器 — 把「启动 + 等待就绪 + 开浏览器」的逻辑全部放进 Python。

为什么不在 .bat 里做：
    bat 的 goto 循环 + netstat|findstr 管道一旦遇到异常输出就会整批脚本终止，
    双击后表现为「窗口一闪、什么都没发生」，且不留任何日志。
    因此 bat 只当薄壳，所有判断逻辑放在这里。

为什么需要「代码指纹」判断：
    后端是 pythonw 常驻进程，改代码不会自动生效。如果只在端口被占用时直接打开
    浏览器，用户就会一直用着旧进程，看到「代码明明改好了、导出还是老样子」。
    所以这里会比较运行中进程的 /api/health.code_fingerprint 与本地现算值：
      一致   → 直接打开浏览器
      不一致 → 自动停掉旧实例、拉起新实例（老版本没有该字段，同样按过期处理）
    这样用户只需要双击桌面图标，改动必然生效，不必记得先杀进程。

用法：
    backend\\venv\\Scripts\\pythonw.exe backend\\scripts\\launch.py
    可选：--no-browser        只启动服务，不打开浏览器
          --timeout 60        等待就绪的最大秒数（默认 60）
          --port 8765         端口（默认 8765，会一并传给后端）
          --restart           无条件停掉旧实例再启动（不等指纹判断）
          --no-auto-restart   发现代码过期也不自动重启，只打开浏览器
          --check             只报告状态（端口/版本/指纹/是否过期），不做任何改动
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

# 输出编码守卫：本脚本输出给用户控制台，保持系统编码（Windows 通常 GBK/cp936），
# 只放宽不可编码字符。若强行改用 UTF-8，经 cmd 的 GBK 控制台会显示成乱码。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, "backend")
VENV_PY = os.path.join(BACKEND, "venv", "Scripts", "python.exe")
VENV_PYW = os.path.join(BACKEND, "venv", "Scripts", "pythonw.exe")
MAIN_PY = os.path.join(BACKEND, "main.py")
LOG_PATH = os.path.join(BACKEND, "data", "launch.log")

if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
    except Exception:
        pass


def local_fingerprint() -> str:
    """当前磁盘上的后端代码指纹。"""
    try:
        from utils.code_fingerprint import compute, count_files
        return compute()
    except Exception as e:
        log(f"警告: 无法计算本地代码指纹（{type(e).__name__}: {e}）")
        return ""


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    """探测端口是否有服务在监听（比 netstat 管道可靠，无编码问题）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex((host, port)) == 0


def read_health(port: int, timeout: float = 3.0):
    """读取运行中服务的 /api/health；读不到返回 None。"""
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def check_running_code(port: int):
    """判断端口上跑的是不是当前代码。返回 (是否最新, 描述)。

    老版本 /api/health 没有 code_fingerprint 字段 —— 那时候代码还没有指纹机制，
    所以只要缺这个字段就一定是过期实例。
    """
    info = read_health(port)
    if info is None:
        return False, "端口有进程在听，但读不到 /api/health"
    remote = info.get("code_fingerprint")
    local = local_fingerprint()
    ver = info.get("version", "?")
    if not remote:
        return False, f"运行中的实例没有代码指纹字段（旧版本，version={ver}）"
    if not local:
        return True, f"无法比对指纹（本地计算失败，version={ver}）"
    if remote != local:
        return False, f"运行中代码 {remote} ≠ 本地代码 {local}（version={ver}）"
    return True, f"代码一致（version={ver}, 指纹 {local}）"


def spawn_backend(port: int) -> bool:
    """以独立进程方式拉起后端（无控制台窗口，父进程退出后继续存活）。"""
    if not os.path.exists(VENV_PY):
        log(f"错误: 未找到虚拟环境 {VENV_PY}")
        log("请先双击 install.bat 完成安装")
        return False

    exe = VENV_PYW if os.path.exists(VENV_PYW) else VENV_PY
    flags = 0
    if os.name == "nt":
        # 独立进程 + 不继承控制台，确保父窗口关闭后服务不死
        flags = (getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                 | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))

    env = dict(os.environ)
    # 强制子进程用 UTF-8，避免中文日志在重定向时触发 UnicodeEncodeError
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # 关掉输出缓冲：日志实时落盘。否则进程被强杀时缓冲区内容丢失，
    # 日志会停在 "Uvicorn running" 而看不到真正的崩溃原因（曾造成误判）。
    env["PYTHONUNBUFFERED"] = "1"

    try:
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as lf:
            lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                     f"spawn: {exe} {MAIN_PY}\n")
            subprocess.Popen(
                [exe, MAIN_PY, "--port", str(port)], cwd=BACKEND, env=env,
                stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                creationflags=flags, close_fds=True)
        log(f"已拉取后端进程 (pid 已分离), 端口 {port}")
        return True
    except Exception as e:
        log(f"错误: 启动失败 {type(e).__name__}: {e}")
        return False


def pid_on_port(port: int) -> int:
    """找出占用该端口的进程 pid（按 GBK 解码 netstat 输出）。取不到返回 0。"""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                             capture_output=True, timeout=20).stdout
        for line in out.decode("gbk", errors="replace").splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[3].upper() == "LISTENING" \
                    and parts[1].endswith(":%d" % port):
                return int(parts[4])
    except Exception:
        pass
    return 0


def backend_pids(port: int):
    """找出本项目后端的所有 python 进程 pid（含未占端口的僵留/重复实例）。

    ⛔ wmic 的 list 格式是「每个属性一行、属性之间夹空行」，不是一条记录一行，
       所以不能按空行切块（那样 CommandLine 与 ProcessId 会落到不同块里）。
       这里改用配对法：记住最近的 CommandLine，遇到 ProcessId 就配成一条记录。
       任何解析异常都不致命 —— 端口占用者会由 pid_on_port() 兜底补上。
    """
    pids = []
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["wmic", "process", "where", "name like 'python%'",
                 "get", "processid,commandline", "/format:list"],
                capture_output=True, timeout=30).stdout
            pending = None
            for raw in out.decode("gbk", errors="replace").splitlines():
                line = raw.strip()
                if not line or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip().lower()
                if key == "commandline":
                    pending = val.strip()
                elif key == "processid":
                    pid, cmd = val.strip(), pending
                    pending = None
                    if not pid.isdigit() or not cmd:
                        continue
                    if MAIN_PY.lower() not in cmd.lower():
                        continue
                    if f"--port {port}" not in cmd:
                        continue
                    pids.append(int(pid))
        except Exception:
            pass

    owner = pid_on_port(port)
    if owner and owner not in pids:
        pids.append(owner)
    return pids


def stop_existing(port: int) -> bool:
    """停掉本项目后端的旧实例（含未占端口的重复进程），并等端口释放。"""
    pids = backend_pids(port)
    if not pids:
        log("没有找到占用端口的旧实例")
        return True
    log(f"发现旧实例 pid={', '.join(str(p) for p in pids)}，正在停止…")
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                           capture_output=True, timeout=20)
        except Exception as e:
            log(f"  停止 pid={pid} 失败: {type(e).__name__}: {e}")

    for _ in range(24):
        if not port_open(port):
            log("旧实例已停止")
            return True
        time.sleep(0.5)
    log(f"旧实例仍占用 {port} 端口，重启中止")
    return False


def report(port: int) -> int:
    """--check：只报告状态，不做任何改动。"""
    print("-" * 56)
    if not port_open(port):
        print(f"  端口 {port}: 无服务在监听")
        print(f"  本地代码指纹: {local_fingerprint()}")
        print("-" * 56)
        return 0
    fresh, why = check_running_code(port)
    info = read_health(port) or {}
    print(f"  端口 {port}: 有服务在运行")
    print(f"  运行版本: {info.get('version', '?')}  |  运行指纹: {info.get('code_fingerprint', '(无)')}")
    print(f"  本地指纹: {local_fingerprint()}")
    print(f"  判定: {'最新' if fresh else '过期（双击桌面图标会自动换新）'}")
    print(f"  依据: {why}")
    pids = backend_pids(port)
    print(f"  本项目后端进程: {', '.join(str(p) for p in pids) or '(未识别)'}")
    print("-" * 56)
    return 0 if fresh else 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--restart", action="store_true",
                    help="无条件停掉旧实例再启动")
    ap.add_argument("--no-auto-restart", action="store_true",
                    help="即使发现运行的是旧代码也不自动重启")
    ap.add_argument("--check", action="store_true",
                    help="只报告运行状态，不做任何改动")
    args = ap.parse_args()

    url = f"http://localhost:{args.port}"

    if args.check:
        return report(args.port)

    if port_open(args.port):
        if not args.restart:
            fresh, why = check_running_code(args.port)
            if fresh:
                log(f"服务已在运行，直接打开 {url}（{why}）")
            elif args.no_auto_restart:
                log(f"注意: 运行中的服务是旧代码（{why}），"
                    f"本次按 --no-auto-restart 只打开浏览器")
            else:
                log(f"检测到运行中的服务不是当前代码（{why}）")
                log("正在自动换新实例，让代码改动生效…")
                if not stop_existing(args.port):
                    return 1
        else:
            if not stop_existing(args.port):
                return 1

    if not spawn_backend(args.port):
        return 1

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        if port_open(args.port):
            log(f"服务已就绪: {url}")
            # 复核一次：确认新实例确实加载了当前代码，避免「换了还是旧的」
            ok, why = check_running_code(args.port)
            log(f"启动校验: {'通过' if ok else '警告'} — {why}")
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        time.sleep(0.8)

    log(f"等待超时（{args.timeout}s），服务可能启动失败")
    log(f"请查看日志: {LOG_PATH}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
