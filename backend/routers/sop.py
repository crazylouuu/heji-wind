"""SOP 资源的 HTTP 接口。

原来 SOP 由 Tauri 的 Rust 命令（`list_sop_files` / `read_sop_file` /
`read_sop_image`）直接读本地磁盘。改成 HTTP 之后：

* 浏览器模式（壳只当启动器）能用；
* 壳窗口模式也走同一套接口，不再需要 invoke；
* 前端只需要一种取数据的方式，少一条分支。

安全：路径来自前端，必须防穿越。所有路径都先 resolve 再校验是否仍在
SOP 根目录内 —— 与 main.py 里 spa_catch 的处理方式一致。
"""

import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from config import sops_dir

router = APIRouter(prefix="/api/sop", tags=["sop"])

# 只允许读取这些后缀（白名单，避免把任意文件当 SOP 读出去）
_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _root() -> Path:
    return sops_dir().resolve()


def _safe_path(rel: str) -> Path:
    """把前端传来的相对路径解析成绝对路径，并确认没有跑出 SOP 根目录。

    穿越攻击的典型形态：`../../backend/config.py`、`..%2f..%2fsecret`。
    这里统一 resolve 后做前缀比对，越界一律 404（不暴露"文件存在但拒绝"）。
    """
    root = _root()
    if not root.is_dir():
        raise HTTPException(status_code=503, detail="SOP 资源目录不存在")

    # 去掉可能的绝对路径与盘符：前端只应传相对路径
    rel = (rel or "").replace("\\", "/").lstrip("/")
    candidate = (root / rel).resolve()

    # 前缀校验必须带分隔符，否则 /sops-extra 会被误判为在 /sops 之内
    if candidate != root and not str(candidate).startswith(str(root) + os.sep):
        raise HTTPException(status_code=404, detail="路径越界")
    return candidate


@router.get("/list")
def list_sops():
    """列出全部 SOP 文件（相对路径 + 分类）。

    分类 = 相对路径的第一段目录名；直接放在根下的文件归为「未分类」。
    """
    root = _root()
    if not root.is_dir():
        raise HTTPException(status_code=503, detail="SOP 资源目录不存在")

    items = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        rel = p.relative_to(root).as_posix()
        parts = rel.split("/")
        category = parts[0] if len(parts) > 1 else "未分类"
        items.append({"path": rel, "category": category})
    return items


@router.get("/file", response_class=PlainTextResponse)
def read_sop(path: str = Query(..., description="相对 assets/sops 的路径")):
    """读取一份 SOP 的原始 Markdown 文本（含 frontmatter）。"""
    p = _safe_path(path)
    if not p.is_file() or p.suffix.lower() not in _TEXT_SUFFIXES:
        raise HTTPException(status_code=404, detail="SOP 文件不存在")
    # 用 utf-8-sig：兼容带 BOM 的文件，避免 frontmatter 首行匹配失败
    return PlainTextResponse(p.read_text(encoding="utf-8-sig"))


@router.get("/image")
def read_sop_image(path: str = Query(..., description="相对 assets/sops 的图片路径")):
    """读取 SOP 里的配图（直接返回二进制，前端用 <img src> 引用即可）。"""
    p = _safe_path(path)
    if not p.is_file() or p.suffix.lower() not in _IMAGE_SUFFIXES:
        raise HTTPException(status_code=404, detail="图片不存在")
    media = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    # 资源随安装包发布、内容不变，可以放心让浏览器缓存
    return FileResponse(p, media_type=media,
                        headers={"Cache-Control": "public, max-age=86400"})
