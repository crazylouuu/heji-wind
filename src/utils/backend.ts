// ============================================================
// backend.ts —— 与 Python 后端（合记 ChemELN 的 FastAPI 服务）通信
//
// 背景：后端原本是独立启动的（桌面图标 / launch.py），
// 与工具箱是两套生命周期。P3 起后端由 Tauri 主壳拉起，
// 前端不再自己找端口、不再自己管令牌——
// 一切从主壳问「后端在哪儿、令牌是多少」。
//
// 用法：
//   const st = await getBackendStatus();   // { running, base_url, token, ... }
//   const exps = await apiGet<Exp[]>("/api/experiments");
//
// 非 Tauri 环境（纯浏览器打开 vite dev server）下，
// invoke 不可用，此时回退到同源相对路径 —— 浏览器直连后端时可用。
// ============================================================
import { invoke } from "@tauri-apps/api/core";

/** 后端状态（与 Rust 侧 BackendStatus 对应） */
export interface BackendStatus {
  /** 后端是否就绪 */
  running: boolean;
  /** 基地址，如 http://127.0.0.1:8765 */
  base_url: string;
  port: number;
  /** 后端进程 PID */
  pid: number | null;
  /** true = 复用了本机已在运行的实例 */
  reused: boolean;
  /** 会话令牌：API 请求要带 X-ChemLab-Token 头 */
  token: string;
  /** 后端版本 */
  version: string;
  /** 失败原因（就绪时为空） */
  error: string | null;
  /** 后端日志路径 */
  log_path: string;
}

/**
 * 非 Tauri 环境（纯浏览器打开 vite dev server）下的回退地址。
 *
 * 注意不能留空：留空会走相对路径 /api/...，打到 vite dev server(1420)
 * 上而不是后端(8765)。浏览器开发时同样需要直连后端。
 */
const DEV_BACKEND_URL =
  (import.meta as { env?: Record<string, string> }).env?.VITE_CHEMLAB_BACKEND ??
  "http://127.0.0.1:8765";

/** 后端不可用时的兜底状态 */
const OFFLINE: BackendStatus = {
  running: false,
  base_url: DEV_BACKEND_URL,
  port: 8765,
  pid: null,
  reused: false,
  token: "",
  version: "",
  error: "未连接到应用主壳",
  log_path: "",
};

let cached: BackendStatus | null = null;

/** 是否运行在 Tauri 里（能 invoke） */
function inTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * 取后端状态。结果会缓存（后端状态在应用生命周期内基本不变），
 * 需要强制刷新时传 force=true。
 */
export async function getBackendStatus(force = false): Promise<BackendStatus> {
  if (cached && !force) return cached;
  if (!inTauri()) {
    // 纯浏览器：没有主壳可问，直接探一下后端
    // （不能假定它在跑 —— 否则状态条会一直显示「已连接」，
    //   实际 iframe 里是一片「无法访问此网站」，误导用户）
    try {
      const res = await fetch(`${DEV_BACKEND_URL}/api/health`, { mode: "cors" });
      const j = await res.json();
      cached = {
        ...OFFLINE,
        running: j?.status === "ok",
        base_url: DEV_BACKEND_URL,
        version: j?.version || "",
        error: j?.status === "ok" ? null : "后端返回异常状态",
      };
    } catch {
      cached = { ...OFFLINE, error: "后端服务未启动（请在桌面应用内打开，或先启动 backend）" };
    }
    return cached;
  }
  try {
    cached = await invoke<BackendStatus>("backend_status");
  } catch (e) {
    cached = { ...OFFLINE, error: String(e) };
  }
  return cached;
}

/** 重启后端（改完 Python 代码热重启用） */
export async function restartBackend(): Promise<BackendStatus> {
  if (!inTauri()) return getBackendStatus();
  try {
    cached = await invoke<BackendStatus>("backend_restart");
  } catch (e) {
    cached = { ...OFFLINE, error: String(e) };
  }
  return cached;
}

/**
 * 拼后端完整 URL。
 * base_url 为空（浏览器直连）时返回相对路径，走同源。
 */
export function apiUrl(path: string, st?: BackendStatus): string {
  const base = (st ?? cached)?.base_url ?? "";
  if (!base) return path;
  return `${base.replace(/\/$/, "")}${path}`;
}

/** 统一的请求头：带会话令牌 */
function authHeaders(st: BackendStatus): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (st.token) h["X-ChemLab-Token"] = st.token;
  return h;
}

let tokenPromise: Promise<string> | null = null;

/**
 * 取会话令牌。
 *
 * Tauri 里：主壳直接把令牌给了我们（status.token）。
 * 纯浏览器里：没有主壳，走 /api/session 引导一次（后端会顺带下发 HttpOnly cookie）。
 */
async function ensureToken(st: BackendStatus): Promise<string> {
  if (st.token) return st.token;
  if (!tokenPromise) {
    tokenPromise = fetch(apiUrl("/api/session", st), { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => (j && j.token) || "")
      .catch(() => "")
      .finally(() => {
        tokenPromise = null;
      });
  }
  return tokenPromise;
}

/** 请求后端 API（GET），自动带令牌 */
export async function apiGet<T>(path: string): Promise<T> {
  const st = await getBackendStatus();
  const token = await ensureToken(st);
  const headers = authHeaders(st);
  if (token) headers["X-ChemLab-Token"] = token;
  const res = await fetch(apiUrl(path, st), {
    method: "GET",
    headers,
    // 跨源时带上凭据（后端会下 HttpOnly cookie）
    credentials: "include",
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || j.error || detail;
    } catch {
      /* 非 JSON 响应，保留状态码 */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

/** 请求后端 API（POST/PUT/DELETE），自动带令牌 */
export async function apiSend<T>(
  method: "POST" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
): Promise<T> {
  const st = await getBackendStatus();
  const token = await ensureToken(st);
  const headers = authHeaders(st);
  if (token) headers["X-ChemLab-Token"] = token;
  const res = await fetch(apiUrl(path, st), {
    method,
    headers,
    credentials: "include",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || j.error || detail;
    } catch {
      /* 非 JSON 响应 */
    }
    throw new Error(detail);
  }
  // 204 / 空响应时返回 null
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

/** 请求后端接口，按**纯文本**返回（SOP 的 Markdown 原文等） */
export async function apiText(path: string): Promise<string> {
  const st = await getBackendStatus();
  const res = await fetch(apiUrl(path, st), {
    method: "GET",
    headers: authHeaders(st),
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.text();
}

/**
 * 请求后端的**二进制**资源，转成 data URL（SOP 配图用）。
 *
 * 为什么不直接写 `<img src="/api/sop/image?path=...">`：
 *   图片请求带不上 `X-ChemLab-Token` 头，只能靠 cookie；
 *   而壳模式下页面在 tauri:// 源、后端在 127.0.0.1，跨源图片请求
 *   不保证带 cookie（SameSite=Lax 会拦），结果就是图片时有时无。
 *   走 fetch + 显式带头，两种模式行为一致。
 */
export async function apiDataUrl(path: string): Promise<string> {
  const st = await getBackendStatus();
  const res = await fetch(apiUrl(path, st), {
    method: "GET",
    headers: { ...(st.token ? { "X-ChemLab-Token": st.token } : {}) },
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("图片读取失败"));
    reader.readAsDataURL(blob);
  });
}
