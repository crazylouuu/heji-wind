# -*- coding: utf-8 -*-
"""ChemELN 访问控制 —— 单机应用的网络暴露面收敛。

背景
----
2026-10-22 安全审计发现：后端原先 ``uvicorn.run(app, host="0.0.0.0")``
监听**所有网卡**，且全部 40+ 个 API 路由**无任何鉴权**，
``CORS_ORIGINS = ["*"]`` 完全放开。后果是：

- 同一局域网内**任何设备**都能直接 ``curl http://<本机IP>:8765/api/experiments``
  读走全部实验记录与化合物库；
- 还能 ``POST`` / ``DELETE`` 篡改或删除数据。

CORS 只约束浏览器端的跨源策略，对 curl / 脚本 / 其它机器的直连请求
**没有任何保护作用**——所以「放开 CORS」不等于「本地安全」。

本模块提供四层防护
------------------
1. **绑定回环**（main.py）：只监听 127.0.0.1，局域网根本连不上。
2. **会话令牌**：启动期生成随机 token，写入数据目录（权限 600）。
   API 请求必须携带 token（header / cookie / query 三选一）。
3. **回环白名单**：即使有人改回 0.0.0.0，非回环来源的请求一律 403。
4. **CORS 收口**：只允许本机来源（config.CORS_ORIGINS）。

令牌传递方式
------------
浏览器与 Tauri 子 webview 都以**同源**方式访问后端，因此：

- 首次加载页面时由中间件下发 ``Set-Cookie``（HttpOnly + SameSite=Strict），
  浏览器后续的 ``fetch`` 自动携带（``credentials`` 默认 ``same-origin``）；
- Tauri 主壳侧可以直接读 token 文件，或用 ``CHEMELN_TOKEN`` 环境变量注入。

三种来源都支持，保证「主壳 → 后端」与「浏览器 → 后端」两条路都能走通。

实现说明
--------
刻意实现为**纯 ASGI 中间件**而非 ``BaseHTTPMiddleware``：
后者在 Starlette 1.6 中对流式响应有已知限制，且会额外引入一层
request/response 包装。纯 ASGI 直接操作 scope 与 send 回调，
行为更可预测，也不影响 SSE / 文件下载等流式端点。
"""
import hmac
import os
import secrets
from pathlib import Path

from config import data_dir, TOKEN_PATH, TOKEN_ENV_VAR

# 免鉴权路径：健康检查（启动器用它探测就绪）与会话引导（换取令牌）
PUBLIC_PATHS = {"/api/health", "/api/session"}

# 令牌请求头名称。
# 2026-10-22 整合期改名：ChemELN → ChemLab。
# 旧名 X-ChemELN-Token 仍然接受（合迹前端与已打开的浏览器标签页还在用）。
TOKEN_HEADER = "x-chemlab-token"
LEGACY_TOKEN_HEADERS = ("x-chemeln-token",)

# 令牌 Cookie 名称（同样新旧双发）
TOKEN_COOKIE = "chemlab_token"
LEGACY_TOKEN_COOKIE = "chemeln_token"

# 受保护的路径前缀（API 与附件）
PROTECTED_PREFIXES = ("/api/", "/attachments/")

# token 缓存：避免每个请求都读盘
_TOKEN_CACHE = None


def load_or_create_token() -> str:
    """取得会话令牌。

    优先级：
    1. 环境变量 ``CHEMLAB_TOKEN``（Tauri 主壳注入，或运维指定固定值）
    2. 数据目录下已存在的 token 文件（重启后保持不变，避免浏览器标签页失效）
    3. 新生成随机 token 并落盘

    落盘时在 POSIX 上设 0600；Windows 依赖用户目录 ACL。
    """
    global _TOKEN_CACHE
    if _TOKEN_CACHE:
        return _TOKEN_CACHE

    env_token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_token:
        _TOKEN_CACHE = env_token
        return _TOKEN_CACHE

    path = Path(TOKEN_PATH)
    try:
        if path.exists():
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                _TOKEN_CACHE = existing
                return _TOKEN_CACHE
    except OSError:
        pass

    token = secrets.token_urlsafe(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # Windows 上没有 POSIX 权限位，忽略
    except OSError:
        # 数据目录不可写时退化为纯内存令牌（本次进程有效，重启后失效）
        pass
    _TOKEN_CACHE = token
    return token


def is_loopback(host: str) -> bool:
    """判断客户端地址是否属于回环网段。"""
    if not host:
        return False
    h = host.strip()
    if h.startswith("::ffff:"):        # IPv4-mapped IPv6
        h = h[len("::ffff:"):]
    if h in ("127.0.0.1", "::1", "localhost"):
        return True
    # 整个 127.0.0.0/8 都是回环
    return h.startswith("127.")


def _parse_cookies(raw: str) -> dict:
    """从 Cookie 头解析出键值对。"""
    out = {}
    for part in raw.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class AccessGuard:
    """纯 ASGI 访问控制中间件。

    用法::

        app.add_middleware(AccessGuard)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers") or []
        hdr = {}
        for key, value in headers:
            name = key.decode("latin-1").lower()
            # 同名 header 取第一个
            hdr.setdefault(name, value.decode("latin-1"))

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # ① 回环白名单：只接受来自本机的请求
        client = scope.get("client")
        client_host = client[0] if client else ""
        if not is_loopback(client_host):
            await self._send_json(send, 403, {
                "error": "Forbidden",
                "detail": "ChemELN 只允许本机访问",
            })
            return

        token = load_or_create_token()

        # ② CORS 预检不带凭据，且不触碰数据 —— 放行给 CORS 中间件处理
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # ③ 受保护路径校验令牌
        needs_auth = any(path.startswith(p) for p in PROTECTED_PREFIXES)
        is_public = path in PUBLIC_PATHS
        if needs_auth and not is_public:
            provided = self._extract_token(hdr, scope)
            if not provided or not hmac.compare_digest(provided, token):
                await self._send_json(send, 401, {
                    "error": "Unauthorized",
                    "detail": "缺少或无效的会话令牌（请从应用界面进入）",
                })
                return

        # ④ 正常放行；若响应是 HTML 且浏览器还没有 cookie，则下发一个
        needs_cookie = (
            not needs_auth
            and TOKEN_COOKIE not in _parse_cookies(hdr.get("cookie", ""))
            and LEGACY_TOKEN_COOKIE not in _parse_cookies(hdr.get("cookie", ""))
        )

        if not needs_cookie:
            await self.app(scope, receive, send)
            return

        # 包裹 send，捕获响应头以便追加 Set-Cookie
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers_list = message.setdefault("headers", [])
                ctype = ""
                for k, v in headers_list:
                    if k.decode("latin-1").lower() == "content-type":
                        ctype = v.decode("latin-1")
                        break
                if "text/html" in ctype:
                    # SameSite=Lax 而非 Strict：
                    #   Strict 会阻断「从 tauri:// 主壳跳转到 http://127.0.0.1:8765」
                    #   这类跨站导航，导致子 webview 拿不到 cookie；
                    #   Lax 仍允许顶级导航携带 cookie，同时阻断跨站 POST
                    #   （即 CSRF 的主要攻击面），是这里的正确平衡点。
                    # 新旧两个 cookie 名都发一份：合迹旧页面认 chemeln_token，
                    # 新页面认 chemlab_token，不用互相迁就。
                    cookie = (
                        f"{TOKEN_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax"
                    )
                    legacy_cookie = (
                        f"{LEGACY_TOKEN_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax"
                    )
                    headers_list.append((b"set-cookie", cookie.encode("latin-1")))
                    headers_list.append((b"set-cookie", legacy_cookie.encode("latin-1")))
            await send(message)

        await self.app(scope, receive, send_wrapper)

    @staticmethod
    def _extract_token(hdr: dict, scope) -> str:
        """从请求中提取令牌：header > cookie > query。

        header 同时认新名（x-chemlab-token）与旧名（x-chemeln-token）。
        """
        for name in (TOKEN_HEADER, *LEGACY_TOKEN_HEADERS):
            header_token = hdr.get(name, "").strip()
            if header_token:
                return header_token

        cookies = _parse_cookies(hdr.get("cookie", ""))
        for name in (TOKEN_COOKIE, LEGACY_TOKEN_COOKIE):
            cookie_token = cookies.get(name, "").strip()
            if cookie_token:
                return cookie_token

        raw_path = scope.get("raw_path") or scope.get("path", "")
        if isinstance(raw_path, bytes):
            raw_path = raw_path.decode("latin-1", "ignore")
        if "token=" in raw_path:
            for seg in raw_path.split("?")[-1].split("&"):
                if seg.startswith("token="):
                    return seg[len("token="):].strip()
        return ""

    @staticmethod
    async def _send_json(send, status: int, payload: dict):
        import json
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        })
        await send({"type": "http.response.body", "body": body})
