# -*- coding: utf-8 -*-
"""后端代码指纹 —— 用来判断「正在跑的进程是不是当前这份代码」。

为什么需要它：
    后端进程是 pythonw 常驻的，改了代码不会自动生效。用户双击桌面快捷方式时，
    launch.py 发现端口已被占用，就只打开浏览器（沿用旧进程），于是「代码明明改
    好了、页面/导出还是老样子」——这类误判极难自查，因为日志看起来一切正常。

    指纹 = 所有后端 .py 文件的 (相对路径, 大小, mtime) 的哈希。同一份代码在同一
    台机器上算出来必然相同；只要有人改动（或 git 切换版本），指纹就变。
    /api/health 会带上运行中进程的指纹，launch.py 拿它和本地现算的比对，
    不一致就说明「跑的是旧代码」→ 自动重启。

本模块只依赖标准库，保证 launch.py（未必有全套依赖）也能安全导入。
"""
import hashlib
import os

# 这些目录里的东西与「代码版本」无关：虚拟环境、数据与附件、字节码缓存
_EXCLUDE_DIRS = {"venv", "data", "__pycache__", ".git", ".idea", ".vscode"}


def backend_dir() -> str:
    """返回 backend/ 目录（本文件位于 backend/utils/ 下）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def compute(root: str = None) -> str:
    """计算后端代码指纹，返回 16 位十六进制字符串。"""
    root = root or backend_dir()
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                st = os.stat(path)
            except OSError:
                continue
            rel = os.path.relpath(path, root).replace("\\", "/")
            items.append((rel, st.st_size, int(st.st_mtime)))

    h = hashlib.sha1()
    h.update(b"chemeln-code-fingerprint-v1\n")
    for rel, size, mtime in sorted(items):
        h.update(f"{rel}|{size}|{mtime}\n".encode("utf-8"))
    return h.hexdigest()[:16]


def count_files(root: str = None) -> int:
    """参与指纹计算的 .py 文件数量（诊断信息用）。"""
    root = root or backend_dir()
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
        n += sum(1 for f in filenames if f.endswith(".py"))
    return n
