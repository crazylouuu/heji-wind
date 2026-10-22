// ============================================================
// appInfo.ts —— 应用元信息（版本号自动跟随 package.json）
// 版本号只在三处维护：package.json / Cargo.toml / tauri.conf.json
// 前端这里自动读取，不再手动写死，避免升级版本时漏改。
// ============================================================
import pkg from "../../package.json";

/** 应用显示名称（P4 起统一为「合记 ChemLab」） */
export const APP_NAME = "合记 ChemLab";

/** 当前版本号（来自 package.json，构建时由 Vite 内联） */
export const APP_VERSION: string = pkg.version;
