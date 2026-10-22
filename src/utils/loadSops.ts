// ============================================================
// loadSops.ts —— SOP 读取与解析
// 数据流动：后端 HTTP 接口读文件 → 这里接收文本 → 拆 frontmatter
//          → js-yaml 解析元数据 → marked 渲染正文 → 返回结构化 SOP
// 类比：这是"SOP 翻译官"。后端把原始文件文本交给你，
//       你把它们翻译成前端能直接使用的结构化数据（Sop 对象）。
//
// 为什么走 HTTP 而不是 Tauri invoke（2026-10-23 改）：
//   壳在「启动器模式」下会退出，界面由浏览器承载 —— invoke 在浏览器里
//   根本不存在（`Cannot read properties of undefined (reading 'invoke')`）。
//   统一走 HTTP 后，壳窗口模式与浏览器模式行为完全一致，少一条分支。
// ============================================================
import { apiGet, apiText } from "./backend";
// js-yaml 的 ESM 版本只有命名导出（load/dump），没有 default 导出
// 所以必须写成 { load as yamlLoad }，不能用 import yaml from "js-yaml"
import { load as yamlLoad } from "js-yaml";
import { marked } from "marked";
import type { Sop, SopFileEntry, RawSopMeta } from "../types/sop";

/// 加载全部 SOP：
/// 1. 让 Rust 列出 assets/sops 下的所有 .md 文件
/// 2. 逐个读取文件内容
/// 3. 解析成结构化 Sop 对象
export async function loadAllSops(): Promise<Sop[]> {
  const files = await apiGet<SopFileEntry[]>("/api/sop/list");
  // Promise.all：多个文件并行读取解析（互不依赖，加快速度）
  const sops = await Promise.all(files.map(loadSopFile));
  return sops;
}

/// 加载单个 SOP 文件：先读文本，再解析
async function loadSopFile(entry: SopFileEntry): Promise<Sop> {
  const raw = await apiText(
    `/api/sop/file?path=${encodeURIComponent(entry.path)}`,
  );
  return parseSop(entry, raw);
}

/// 解析一条 SOP：拆 frontmatter → 解析元数据 → 渲染正文
export function parseSop(entry: SopFileEntry, raw: string): Sop {
  const { metaRaw, bodyMd } = splitFrontmatter(raw);
  const meta = parseMeta(metaRaw, entry.category);
  const bodyHtml = marked.parse(bodyMd) as string;
  return { fileName: entry.path, meta, bodyMd, bodyHtml };
}

/// 拆分 frontmatter（YAML 元数据区）和正文（Markdown 内容）
/// frontmatter 规则：文件第一行是 ---，遇到下一个 --- 结束
export function splitFrontmatter(raw: string): { metaRaw: string; bodyMd: string } {
  const lines = raw.split("\n");
  // 第一行不是 ---：说明没有元数据区，整篇都当正文
  if (lines[0]?.trim() !== "---") {
    return { metaRaw: "", bodyMd: raw };
  }
  // 找第二个 ---（从第 2 行开始找，跳过开头那个）
  const end = lines.findIndex((l, i) => i > 0 && l.trim() === "---");
  if (end === -1) {
    // 只有开头一个 ---：当作格式错误，整篇当正文（不崩溃）
    return { metaRaw: "", bodyMd: raw };
  }
  return {
    metaRaw: lines.slice(1, end).join("\n"),
    bodyMd: lines.slice(end + 1).join("\n"),
  };
}

/// 解析 YAML 元数据
/// 关键设计：字段缺失给默认值、YAML 写错不抛异常——
/// 用户自己写的 SOP 偶尔不规范，不能让"一个坏文件"搞垮整个列表
function parseMeta(metaRaw: string, fallbackCategory: string): Sop["meta"] {
  let raw: RawSopMeta = {};
  try {
    raw = (yamlLoad(metaRaw) as RawSopMeta) ?? {};
  } catch {
    raw = {}; // YAML 解析失败：全部字段走默认值
  }
  return {
    id: raw.id ?? "unknown",
    title: raw.title ?? "未命名 SOP",
    category: raw.category ?? fallbackCategory,
    tags: raw.tags ?? [],
    risk: raw.risk ?? "待评估",
    scale: raw.scale,
    temperature: raw.temperature,
    time: raw.time,
    references: raw.references ?? [],
  };
}
