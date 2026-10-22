# -*- coding: utf-8 -*-
"""ChemLab 统一配置：版本、端口、路径。数据目录唯一来源。

三应用整合后的变化（2026-10-22）：
- 产品名从「合迹 ChemELN」改为「合记 ChemLab」
- 数据目录从 %APPDATA%\\ChemELN 改为 %APPDATA%\\ChemLab，
  数据库名从 chemeln.db 改为 chemlab.db（统一 schema，16 表）
- 安全加固保留：只监听回环 + 会话令牌 + 回环白名单 + CORS 收口

模式说明：
- 源码模式：数据目录 = %APPDATA%\\ChemLab（与迁移脚本、打包版保持一致，
  避免「开发一套路径、生产另一套路径」的迁移陷阱）
- 打包模式：数据目录同样在 %APPDATA%\\ChemLab，程序目录只读、数据外置防丢失

所有模块（database / routers / utils）统一从这里取 DB_PATH、ATTACH_DIR、
BACKUP_DIR，不再各自拼路径。
"""
import os
import sys
from pathlib import Path

APP_NAME = "合记 ChemLab"
APP_NAME_EN = "ChemLab"
APP_VERSION = "0.1.0-integ"  # 整合版基线（README 徽章 / 页脚同步）
DEFAULT_PORT = 8765

# 只监听回环地址 —— 2026-10-22 安全加固（chemELN 阶段完成，整合版保留）。
# 原先绑定 "0.0.0.0" 会让同一局域网内任何设备直连本机 API
#（且当时全部路由无鉴权），改为 127.0.0.1 后局域网根本无法连接。
BIND_HOST = "127.0.0.1"

# CORS 收口：只允许本机来源。
# 原先为 ["*"]（完全放开）。注意 CORS 只约束浏览器跨源策略，
# 对 curl / 脚本直连无保护 —— 真正的防线是 BIND_HOST + 令牌鉴权。
# Tauri 子 webview 与浏览器同源（http://127.0.0.1:<port>），本来就同源，
# 不依赖 CORS；这里保留本机白名单以兼容潜在的跨源调用场景。
CORS_ORIGINS = [
    "http://127.0.0.1",
    "http://localhost",
    "http://tauri.localhost",
    "tauri://localhost",
    # Vite 开发服务器（pnpm dev 默认 1420 端口）——
    # 开发时工具箱前端在 1420，直接 fetch 8765 属于跨源，需要显式放行。
    "http://localhost:1420",
    "http://127.0.0.1:1420",
]

# 会话令牌相关
TOKEN_ENV_VAR = "CHEMLAB_TOKEN"       # Tauri 主壳注入时使用
TOKEN_FILENAME = ".session_token"      # 落在数据目录下，重启后保持不变


def is_frozen() -> bool:
    """是否运行于 PyInstaller 打包环境。"""
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    """资源根目录：源码模式=仓库根；打包模式=PyInstaller 解压目录(_MEIPASS)。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # backend/config.py -> 仓库根
    return Path(__file__).resolve().parent.parent


def backend_dir() -> Path:
    return resource_root() / "backend"


def frontend_dir() -> Path:
    """前端静态资源目录。

    查找顺序：
    1. `frontend/` —— 打包模式随 _MEIPASS 解压出来的前端
    2. `frontend-chemeln/` —— 仓库内的合迹前端（P4 起由后端托管，
       供主壳的「实验记录」页 iframe 嵌入；P5 换成原生子 webview 后
       仍由后端提供这份资源）

    两者都不存在时返回 frontend/（调用方会走「前端未构建」分支）。
    """
    root = resource_root()
    for name in ("frontend", "frontend-chemeln"):
        p = root / name
        if p.exists():
            return p
    return root / "frontend"


def sops_dir() -> Path:
    """SOP 资源目录（18 份 Markdown + 配图）。

    查找顺序：
    1. `<资源根>/assets/sops`  —— 打包模式（PyInstaller datas）
    2. `<资源根>/backend/../assets/sops` —— 源码模式（仓库根/assets/sops）

    两者都没有时返回第 1 个，调用方据 `is_dir()` 判定。
    """
    return resource_root() / "assets" / "sops"


def toolbox_dir() -> Path:
    """工具箱前端（Vue SPA）静态资源目录 —— 「不用 Tauri 壳」模式下的入口。

    查找顺序：
    1. `<资源根>/frontend-toolbox`          —— 打包模式（PyInstaller datas 解压）
    2. `<资源根>/backend/frontend-toolbox`  —— 源码模式（pnpm build 后复制过来）

    两者都没有时返回第 2 个路径，调用方据 `exists()` 判定是否挂载 ——
    不存在就不挂载，完全不影响现有的壳模式。
    """
    root = resource_root()
    for p in (root / "frontend-toolbox", root / "backend" / "frontend-toolbox"):
        if p.exists():
            return p
    return root / "backend" / "frontend-toolbox"


def data_dir() -> Path:
    """用户数据目录（自动创建 attachments / backups 子目录）。

    - 源码模式与打包模式一致：都用 %APPDATA%\\ChemLab
      （整合后刻意统一，避免开发/生产两套路径导致的迁移陷阱）

    目录内容：
        chemlab.db          统一库（16 表）
        .session_token      会话令牌（安全加固，权限 0600）
        attachments/       上传的附件（图片/PDF/NMR 等）
        backups/           自动与手动备份
    """
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    p = Path(base) / APP_NAME_EN
    p.mkdir(parents=True, exist_ok=True)
    (p / "attachments").mkdir(exist_ok=True)
    (p / "backups").mkdir(exist_ok=True)
    return p


# 模块级兼容常量：各模块 import 后用法不变，仅路径来源统一到 data_dir()
DB_PATH = str(data_dir() / "chemlab.db")
ATTACH_DIR = str(data_dir() / "attachments")
BACKUP_DIR = str(data_dir() / "backups")
TOKEN_PATH = str(data_dir() / TOKEN_FILENAME)

