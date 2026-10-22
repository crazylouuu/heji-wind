// ============================================================
// favorites.ts —— 收藏功能（Day 4）
// 存储方式：localStorage 里存一个 SOP id 数组：
//   ["alkylation-001", "oxidation-001", ...]
// 首页用它展示"我的收藏"，详情页用它切换 ★ 状态。
// ============================================================

/** 存储键 */
const STORAGE_KEY = "heji_favorites";

/// 读出全部收藏的 SOP id 列表
export function getFavorites(): string[] {
  try {
    const arr = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(arr) ? arr : [];
  } catch {
    return []; // 数据损坏时当作没有收藏，不崩溃
  }
}

/// 判断某个 SOP 是否已收藏
export function isFavorite(id: string): boolean {
  return getFavorites().includes(id);
}

/// 切换收藏状态；返回切换后的状态（true = 现在已收藏）
export function toggleFavorite(id: string): boolean {
  const list = getFavorites();
  const idx = list.indexOf(id);
  if (idx >= 0) {
    list.splice(idx, 1);        // 已收藏 → 移除
  } else {
    list.push(id);              // 未收藏 → 添加
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list)); // 存回
  return idx < 0;
}
