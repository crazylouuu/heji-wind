// ============================================================
// calcHistory.ts —— 计算器历史记录（Day 5，后调整）
// 存储：localStorage 存数组，最多保留 10 条，新的在前。
// 覆盖规则：第 11 次保存时，最旧的第 1 条被覆盖（先进先出）。
// 每条记录：时间 + 模块名 + 结果摘要（投料计划表的摘要=完整表格文本）。
// ============================================================

/** 一条计算历史 */
export interface CalcRecord {
  time: string;    // 记录时间（形如 12:30:05）
  module: string;  // 模块名（如 "投料计划"）
  summary: string; // 结果摘要（投料计划表 = 完整表格文本，可含换行）
}

/** 存储键 */
const STORAGE_KEY = "heji_calc_history";

/** 最大保留条数：10（第 11 次保存覆盖最旧 1 条） */
const MAX_RECORDS = 10;

/// 读出历史记录（数据损坏时返回空数组）
export function getHistory(): CalcRecord[] {
  try {
    const arr = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

/// 新增一条历史（插到最前面；超过 10 条时自动去掉最旧一条）
export function addHistory(record: CalcRecord): void {
  const list = getHistory();
  list.unshift(record);
  // 超限时截断数组末尾 = 覆盖最旧的记录（先进先出）
  if (list.length > MAX_RECORDS) list.length = MAX_RECORDS;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

/// 清空历史（设置页将来可能用到）
export function clearHistory(): void {
  localStorage.removeItem(STORAGE_KEY);
}
