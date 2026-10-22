# -*- coding: utf-8 -*-
"""后端日志配置 —— 打包版的关键适配。

为什么需要它
------------
打包版（PyInstaller ``console=False``）**没有 stdout/stderr**：
``sys.stdout`` 是 ``None``，print 会直接抛异常（main.py 里有 devnull 兜底，
但那样就彻底看不到任何日志了）。

而「后端起没起来、报了什么错」恰恰是打包后最需要的信息 ——
用户双击应用，窗口空白，主壳只告诉你「后端未就绪」，
没有日志就完全无从下手。

所以这里把日志**同时**写到：

1. ``%APPDATA%\\ChemLab\\logs\\backend.log``（追加，永久留痕）
2. stdout（源码模式下有用，打包版自动跳过）

实现要点
--------
- 只能用标准库 ``logging``，不引第三方依赖
- uvicorn 自己的 access log / error log 也要引到同一个文件，
  否则文件里只有应用日志，缺请求记录
- 编码固定 UTF-8（Windows 默认 GBK，日志里有中文 emoji 会炸）
"""
import logging
import os
import sys
from pathlib import Path


def log_dir() -> Path:
    """日志目录：%APPDATA%\\ChemLab\\logs（与主壳读的是同一处）。"""
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    p = Path(base) / "ChemLab" / "logs"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return p


def log_file() -> Path:
    return log_dir() / "backend.log"


def setup_logging(level: str = "INFO") -> Path:
    """配置根 logger，把日志同时输出到文件与控制台。

    返回日志文件路径（打不开时返回预期路径，调用方可据此提示用户）。
    """
    path = log_file()
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件句柄：打不开就只留控制台，不要因此让整个应用起不来
    file_ok = False
    try:
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        file_ok = True
    except OSError:
        pass

    # 控制台：打包版没有 stdout（sys.stdout is None），此时跳过
    try:
        if sys.stdout is not None and getattr(sys.stdout, "write", None):
            sh = logging.StreamHandler(sys.stdout)
            sh.setFormatter(fmt)
            root.addHandler(sh)
    except Exception:
        pass

    if file_ok:
        logging.getLogger("chemlab").info("后端日志已就绪: %s", path)
    return path


def redirect_uvicorn_logging() -> None:
    """把 uvicorn 的日志接到根 logger（否则它们只往 stdout 写，打包版就没了）。"""
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
