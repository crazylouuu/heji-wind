// ============================================================
// stepChecklist.ts —— 步骤勾选状态的本地持久化
// 作用：把"哪些步骤打勾了"存到浏览器 localStorage。
// 好处：关掉应用再打开，勾选状态还在（离线本地，不上传云端）。
// 存储结构（一个 JSON 对象）：
//   { "alkylation-001": { "1": true, "2": false, "3": true }, ... }
//   └── SOP 的 id ──┘   └─ 步骤编号 → 是否勾选 ─┘
// ============================================================

/** 存储键：全局唯一，避免和别的数据撞名 */
const STORAGE_KEY = "heji_sop_step_checks";

/** 完整数据结构：SOP id → 步骤编号 → 是否勾选 */
type CheckMap = Record<string, Record<number, boolean>>;

/// 读出全部勾选数据（JSON 解析失败时返回空对象，不崩溃）
function readAll(): CheckMap {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as CheckMap;
  } catch {
    return {};
  }
}

/// 读出某个 SOP 的勾选状态：{ 步骤编号: 是否勾选 }
export function getStepChecks(sopId: string): Record<number, boolean> {
  return readAll()[sopId] ?? {};
}

/// 设置某个步骤的勾选状态并保存
export function setStepCheck(sopId: string, stepIndex: number, checked: boolean): void {
  const all = readAll();
  const one = all[sopId] ?? {};
  one[stepIndex] = checked;           // 写入这一步的状态
  all[sopId] = one;                   // 放回总表
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all)); // 存回浏览器
}

/// 计算已勾选的步骤数（详情页显示"已完成 x/y"进度用）
export function getCheckedCount(sopId: string): number {
  const one = getStepChecks(sopId);
  return Object.values(one).filter(Boolean).length; // 只数 true 的
}
