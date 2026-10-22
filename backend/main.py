"""
ChemLab — 统一的化学实验工作台后端
Main FastAPI application.
Run: python main.py  →  http://127.0.0.1:8765
"""
import os
import sys
import shutil

# Ensure backend dir is in path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, get_db, DB_PATH, ATTACH_DIR
from routers import experiments, compounds, templates, search, data, lab, sop
from config import (APP_VERSION, CORS_ORIGINS, DEFAULT_PORT, BIND_HOST,
                    frontend_dir, is_frozen, toolbox_dir)
from utils.code_fingerprint import compute as _compute_code_fingerprint
from utils.security import AccessGuard
from utils.logging_setup import setup_logging, redirect_uvicorn_logging

# 打包版（PyInstaller console=False）没有 stdout，print 会抛异常；
# 统一走 logging，源码模式打控制台、打包模式落文件。
_LOG_FILE = setup_logging()
redirect_uvicorn_logging()


def _log(msg: str) -> None:
    """统一的日志输出（替代裸 print）。"""
    import logging
    logging.getLogger("chemlab").info(msg)


def _is_managed_by_shell() -> bool:
    """是否由 Tauri 主壳拉起（主壳负责界面与生命周期）。"""
    import os
    return (os.environ.get("CHEMLAB_PARENT") or "").lower() == "tauri"

# 启动时算一次：所有后端 .py 的 (路径, 大小, mtime) 哈希。
# launch.py 用它判断「端口上跑的是不是当前这份代码」，不一致就自动重启换新。
# ⛔ 合并说明：版本号唯一真源已改为 backend/config.py 的 APP_VERSION。
CODE_FINGERPRINT = _compute_code_fingerprint()


def _resolve_port() -> int:
    """从命令行解析端口。

    放在模块级是为了让 startup 日志能打印真实端口
    （之前这里硬编码 DEFAULT_PORT，用 --port 启动时日志会写错）。
    parse_known_args 不会误伤 uvicorn 的其它参数。
    """
    import argparse
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args, _ = ap.parse_known_args()
    return args.port


PORT = _resolve_port()

app = FastAPI(title="ChemLab", version=APP_VERSION,
              description="Unified chemistry lab workbench backend")

# CORS：只允许本机来源（2026-10-22 安全加固，原为 ["*"] 完全放开）
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 访问控制：回环白名单 + 会话令牌（2026-10-22 安全加固）
# 注意顺序：Starlette 的 add_middleware 用 insert(0, ...)，
# 后添加的中间件位于更外层 —— 因此 AccessGuard 会先于 CORS 执行，
# 未授权请求直接 401/403，不会走到 CORS 逻辑。
app.add_middleware(AccessGuard)

# Register routers
app.include_router(experiments.router)
app.include_router(compounds.router)
app.include_router(templates.router)
app.include_router(search.router)
app.include_router(data.router)
# P5：子 webview ↔ 主壳 的事件中转（详见 routers/lab.py 顶部说明）
app.include_router(lab.router)
# SOP 资源（原由 Tauri 命令直接读盘；改成 HTTP 后浏览器模式也能用）
app.include_router(sop.router)

# Static files for attachments
os.makedirs(ATTACH_DIR, exist_ok=True)
# ---------------------------------------------------------------------------
# 静态资源缓存策略
#
# 为什么需要它：StaticFiles 默认不发 Cache-Control，浏览器就会启用
# 「启发式缓存」（大致取 (now - last-modified) 的 10%）。后果是前端更新后，
# 用户打开还是旧界面 —— 因为缓存的旧 index.html 仍指向旧的 JS 文件名。
# 这个坑在 2026-10-27 改侧栏导航时实际踩到过：装好的新版打开仍显示旧的
# 顶部导航，必须手动 Ctrl+F5 才能看到新的左侧栏。
#
# 策略（业界标准做法）：
#   index.html / 其它 html  → no-cache（每次都回源验证，文件没变就 304，很便宜）
#   assets/*.js|css|图片     → 一年 + immutable（文件名带内容 hash，内容变了名字就变）
# ---------------------------------------------------------------------------
class CacheAwareStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)

        # 用 Content-Type 判断而不是猜 path 的形式 —— 目录请求（/toolbox/）
        # 传给 get_response 的 path 可能是 ""、"."

        # 或 "./index.html"，按字符串比容易漏。
        ctype = (resp.headers.get("content-type") or "").lower()
        name = "/" + (path or "").replace("\\", "/").strip("/").lower()

        if "text/html" in ctype:
            # 入口文件绝不能被启发式缓存
            resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        elif "/assets/" in name:
            # 打包产物文件名含内容 hash，内容变了名字就变 → 可安全长缓存
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            # 其它静态文件（图片、favicon 等）：短缓存，兼顾更新
            resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp


app.mount("/attachments", StaticFiles(directory=ATTACH_DIR), name="attachments")

# Serve frontend (built SPA) — 打包模式下从 _MEIPASS 解压目录读取
FRONTEND_DIR = str(frontend_dir())
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", CacheAwareStaticFiles(directory=FRONTEND_DIR), name="static")

# 工具箱前端（Vue SPA，hash 路由）——「不用 Tauri 壳」模式下的入口
#
# Vue 用的是 createWebHashHistory（#/sops 这类地址），所以不需要 catch-all：
# 只要 index.html 和 assets 能被静态服务取到即可。
# 浏览器模式下 apiUrl() 返回相对路径，与页面同源，API 调用天然正确。
# 目录不存在时跳过 —— 不影响现有的壳模式。
TOOLBOX_DIR = str(toolbox_dir())
if os.path.exists(TOOLBOX_DIR):
    app.mount("/toolbox", CacheAwareStaticFiles(directory=TOOLBOX_DIR, html=True), name="toolbox")


@app.on_event("startup")
def startup():
    init_db()
    _log(f"Database: {DB_PATH}")
    _log(f"Attachments: {ATTACH_DIR}")
    _log(f"Frontend: {FRONTEND_DIR}")
    # 启动后台自动备份线程（按设置定时备份 DB + 附件）
    try:
        from utils.auto_backup import start_scheduler
        start_scheduler()
        _log("Auto-backup scheduler started")
    except Exception as e:
        _log(f"Auto-backup disabled: {e}")
    _log(f"Ready at http://{BIND_HOST}:{PORT}")
    _log(f"Version: {APP_VERSION} | code fingerprint: {CODE_FINGERPRINT}")
    _log(f"Log file: {_LOG_FILE}")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ChemLab", "version": APP_VERSION,
            # 运行中进程的代码指纹：与磁盘上现算的值不同 = 跑的是旧代码
            "code_fingerprint": CODE_FINGERPRINT,
            # 磁盘上现算的指纹：Tauri 主壳据此判断「端口上这个实例是不是当前这份代码」，
            # 不一致时可以选择重启而不是复用（否则改了 Python 代码却还在用旧进程）
            "disk_fingerprint": _compute_code_fingerprint()}


@app.get("/api/session")
def session():
    """会话引导：返回当前会话令牌。

    免鉴权（与 /api/health 同级）—— 因为调用方正是要「换取」令牌。
    安全性由两层保证：
    1. 访问控制中间件已拦截非回环来源，局域网根本到不了这里；
    2. 本机上的其它进程/页面理论上能取到令牌，但它们本来就能直接
       读 %APPDATA%\\ChemLab\\chemlab.db，威胁模型上等价。
    """
    from utils.security import load_or_create_token
    return {"token": load_or_create_token(), "version": APP_VERSION}


@app.get("/")
def index():
    """Serve the main SPA (never cached, so JS/CSS version bumps always take effect)."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        })
    return JSONResponse({"message": "ChemLab API running. Frontend not built yet."})


# Catch-all for SPA routing
@app.get("/{full_path:path}")
def spa_catch(full_path: str):
    """Serve SPA for any non-API route."""
    if full_path.startswith("api/") or full_path.startswith("attachments/"):
        return JSONResponse({"error": "Not found"}, status_code=404)

    # 路径穿越防护（2026-10-22 安全加固）：
    # os.path.join 不会规范化 ".."，原先 ../backend/config.py 之类能被 isfile
    # 命中并读出 frontend 目录之外的文件。这里先规范化再校验前缀，
    # 越界一律当作不存在（回落到 index.html）。
    file_path = os.path.normpath(os.path.join(FRONTEND_DIR, full_path))
    frontend_root = os.path.normpath(FRONTEND_DIR)
    if not (file_path == frontend_root
            or file_path.startswith(frontend_root + os.sep)):
        file_path = ""  # 越界 → 不提供静态文件

    # Try to serve static file
    if file_path and os.path.isfile(file_path):
        return FileResponse(file_path)

    # Fall back to index.html for SPA routes
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
        })
    return JSONResponse({"error": "Not found"}, status_code=404)


if __name__ == "__main__":
    # PyInstaller console=False 时 sys.stdout/stderr 可能为 None，print 会崩溃；
    # 用 devnull 兜底（B 黄河化学同款修复，main.py 已验证有效）。
    for _s in (sys.stdout, sys.stderr):
        if _s is None:
            sys.stdout = sys.stderr = open(os.devnull, "w")
            break


    # If the port is already in use, another instance is running.
    # Exit silently so logon auto-start (startup folder) never double-starts.
    # NOTE: plain bind() is unreliable here because uvicorn sets SO_REUSEADDR;
    # use Windows-only SO_EXCLUSIVEADDRUSE for a true exclusive probe.
    import socket
    _probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        _probe.bind((BIND_HOST, PORT))
        _probe.close()
    except OSError:
        # 端口已被占用：说明已有实例在跑。
        # 被 Tauri 主壳拉起时（CHEMLAB_PARENT=tauri）：什么都不做，静默退出 ——
        #   主壳会检测到「端口已有健康实例」并直接复用，不该在这里弹浏览器。
        # 独立运行的打包版：把浏览器开到现有实例上（双击图标 = 打开应用，而不是没反应）。
        # 源码版：静默退出（launch.py / 开机自启不重复启动）。
        if is_frozen() and not _is_managed_by_shell():
            import webbrowser
            try:
                webbrowser.open(f"http://127.0.0.1:{PORT}")
            except Exception:
                pass
        else:
            _log("Port %d already in use - another instance is running, exiting." % PORT)
        sys.exit(0)

    import uvicorn
    # 打包版（无控制台窗口）：服务就绪后自动打开默认浏览器（源码版由 launch.py 负责）
    # 但被主壳拉起时不开 —— 主壳里已经有界面了，再弹浏览器是画蛇添足。
    if is_frozen() and not _is_managed_by_shell():
        import threading
        import time
        import webbrowser
        _url = f"http://127.0.0.1:{PORT}"

        def _open_browser():
            time.sleep(1.8)   # 等 uvicorn 真正监听
            try:
                webbrowser.open(_url)
            except Exception:
                pass

        threading.Thread(target=_open_browser, daemon=True).start()
    # 只监听回环地址（2026-10-22 安全加固，原为 "0.0.0.0" 会暴露到局域网）
    uvicorn.run(app, host=BIND_HOST, port=PORT)
