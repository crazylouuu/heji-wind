// ============================================================
// searchSops.ts —— SOP 全局搜索（Day 4 改进版）
// 搜索范围：标题、标签、正文全文（含试剂表、步骤中的现象描述）
// 匹配方式：
//   1. 原文包含（中文/英文关键词，如 "烷基化"、"H2O"）
//   2. 拼音匹配（自己生成拼音索引，不依赖 match API）：
//      - 全拼索引：全文每个字转拼音后拼接（"mubanwanjihuafanying..."）
//      - 首字母索引：每字拼音首字母拼接（"mbwjhfy..."）
//      - 输入 "wjh"（首字母）或 "wanjihua"（全拼）都命中
// 类比：给每本书做两张拼音卡片（全拼卡 + 首字母卡），
//       查书时看哪张卡上有你要的拼音。
// ============================================================
import { pinyin } from "pinyin-pro";
import type { Sop } from "../types/sop";

/// 把一段文字转成两张拼音索引（全拼 + 首字母）
function pinyinIndexes(text: string): { full: string; first: string } {
  // pinyin(text, { type: "array" })：每个字符对应一个拼音/原文，返回数组
  // toneType: "none" 去掉声调；pattern: "first" 只取首字母
  const full = pinyin(text, { toneType: "none", type: "array" })
    .join("")
    .replace(/\s+/g, ""); // 去掉空白，保证子串连续
  const first = pinyin(text, { pattern: "first", toneType: "none", type: "array" })
    .join("")
    .replace(/\s+/g, "");
  return { full, first };
}

/// 判断一个 SOP 是否匹配搜索词；搜索词为空时返回 true（全部显示）
export function matchesSop(sop: Sop, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true; // 没输入内容 = 不过滤

  // 把标题、标签、正文拼成一段"可搜索全文"
  const text = [sop.meta.title, ...sop.meta.tags, sop.bodyMd].join(" ");

  // 第 1 种匹配：原文直接包含关键词（不区分大小写）
  if (text.toLowerCase().includes(q)) return true;

  // 第 2 种匹配：拼音（全拼或首字母）
  const { full, first } = pinyinIndexes(text);
  if (full.includes(q) || first.includes(q)) return true;

  return false;
}
