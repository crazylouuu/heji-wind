// ============================================================
// settings.ts —— 应用设置（Day7）
// 管理：字体大小、手套模式
// 存储：localStorage（纯前端状态，离线可用）
// 类比：这里是"控制面板"的记忆——你调完旋钮，
//       它把状态记在小本子上，下次开机按本子恢复。
// ============================================================

// 字体大小三档
export type FontScale = "small" | "medium" | "large";

export interface AppSettings {
  fontScale: FontScale;   // 字体（整体缩放）档位
  gloveMode: boolean;     // 手套模式（按钮更大）
}

// localStorage 的键名
const KEY = "heji_settings";

// 默认设置（新用户第一次打开的初始状态）
const DEFAULTS: AppSettings = {
  fontScale: "medium",
  gloveMode: false,
};

/// 读取设置：localStorage 里没有就返回默认值；
/// 有就"默认值 + 已存值"合并（将来新增设置项时旧数据不丢）
export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS }; // 数据损坏时退回默认，不崩溃
  }
}

/// 保存设置
export function saveSettings(s: AppSettings) {
  localStorage.setItem(KEY, JSON.stringify(s));
}

/// 把设置"落地"到界面（每次启动或设置变化时调用）：
/// 1. 字体大小 → 用 zoom 整体缩放（WebView2 是 Chromium，支持 zoom）
/// 2. 手套模式 → 给 <html> 加 glove class，按钮自动变大
///
/// 注：深色模式已于 2026-10-27 移除 —— 这是电脑端实验室工具，
/// 环境光照稳定，多一套主题只增加维护成本。
export function applySettings() {
  const s = loadSettings();

  // 字体：整体缩放（0.9 / 1.0 / 1.1）
  const zoom = s.fontScale === "small" ? 0.9 : s.fontScale === "large" ? 1.1 : 1.0;
  document.documentElement.style.zoom = String(zoom);

  // 手套模式
  document.documentElement.classList.toggle("glove", s.gloveMode);
}
