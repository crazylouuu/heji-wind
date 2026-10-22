# -*- coding: utf-8 -*-
"""子 webview ↔ 主壳 的事件中转（P5）。

为什么需要它
------------
P5 用 Tauri 原生子 webview 嵌入实验记录页。子 webview 加载的是
``http://127.0.0.1:8765/``（远程 origin），有两件事做不到：

1. **不能用 Tauri IPC**：``is_local_url()`` 只认 ``tauri://`` 或 devUrl 相对路径，
   远程 origin 的 webview 调不了 Tauri 自定义命令。
2. **``on_page_load`` 触发不可靠**：实测有时触发有时不触发，
   与页面真实加载状态不同步，不能用它判断"子页就绪了"。

于是走一条干净的路：**子页 → 后端 → 主壳**。

- 子页与后端同源（都是 127.0.0.1:8765），``fetch('/api/lab/events')`` 天然可用；
- 主壳与后端也通（主壳在同机，且已拿到会话令牌）；
- 后端在中间当一个极简的消息队列（进程内内存，几十条足够）。

主壳 → 子页则走 Rust ``eval()`` 注入（方案实测 12/12 成功），不需要本模块。

数据只存在内存里：主壳与后端同生命周期，后端重启后事件自然清空。
"""
from collections import deque
from typing import Any, Dict, List

from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/lab", tags=["lab"])

# 事件环形缓冲：只保留最近 50 条
_EVENTS: deque = deque(maxlen=50)

# 自增序号：主壳用 since 拉增量
_SEQ = 0


@router.post("/events")
def push_event(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """子页上报事件。

    例：``{"event": "ready"}`` —— 页面加载完成；
        ``{"event": "nav", "payload": {"view": "experiments"}}`` —— 视图切换。
    """
    global _SEQ
    _SEQ += 1
    _EVENTS.append(
        {
            "seq": _SEQ,
            "event": str(payload.get("event", ""))[:64],
            "payload": payload.get("payload", {}),
        }
    )
    return {"ok": True, "seq": _SEQ}


@router.get("/events")
def pull_events(since: int = 0) -> Dict[str, Any]:
    """主壳拉取增量事件。"""
    events: List[Dict[str, Any]] = [e for e in _EVENTS if e["seq"] > since]
    return {"seq": _SEQ, "events": events}


@router.get("/reset")
def reset_events() -> Dict[str, Any]:
    """清空事件（主壳重新打开实验记录页时调用，避免读到上一次的 ready）。"""
    global _SEQ
    _EVENTS.clear()
    _SEQ = 0
    return {"ok": True, "seq": 0}
