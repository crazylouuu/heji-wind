// ============================================================
// checklist.ts —— 实验检查清单（Day 6）
// 预设 5 组通用安全/操作提醒（无水无氧、低温、氢化、柱层析、放大）。
// 注意：这里只有"通用操作提醒"，不含任何具体危险化学品的
//       合成步骤或操作细节 —— 安全约束。
// 存储：localStorage 保存全部项（含勾选状态和自定义项）。
// ============================================================

/** 一条检查项 */
export interface ChecklistItem {
  id: string;     // 唯一标识
  group: string;  // 所属组（无水无氧/低温/氢化/柱层析/放大/自定义）
  text: string;   // 检查内容
  checked: boolean; // 是否已勾选
}

/** 存储键 */
const KEY = "heji_checklist";

/// 预设检查项（通用框架，所有实验室共用）
const PRESET: ChecklistItem[] = [
  // 无水无氧
  { id: "p1", group: "无水无氧", text: "确认体系密封性，无漏气点", checked: false },
  { id: "p2", group: "无水无氧", text: "溶剂/试剂除水处理已确认", checked: false },
  { id: "p3", group: "无水无氧", text: "惰性气体保护已开启", checked: false },
  // 低温
  { id: "p4", group: "低温", text: "温度计/低温浴温度已校准", checked: false },
  { id: "p5", group: "低温", text: "降温至目标温度并稳定后再加料", checked: false },
  { id: "p6", group: "低温", text: "加料速度已控制（缓慢滴加）", checked: false },
  // 氢化
  { id: "p7", group: "氢化", text: "氢源状态与压力表读数已确认", checked: false },
  { id: "p8", group: "氢化", text: "体系置换与排空操作完成", checked: false },
  { id: "p9", group: "氢化", text: "密封性与防泄漏检查完成", checked: false },
  // 柱层析
  { id: "p10", group: "柱层析", text: "装柱均匀、无气泡断层", checked: false },
  { id: "p11", group: "柱层析", text: "上样方式与洗脱梯度已规划", checked: false },
  { id: "p12", group: "柱层析", text: "TLC 跟踪频次已定", checked: false },
  // 放大
  { id: "p13", group: "放大", text: "反应容器容量与装填率核对", checked: false },
  { id: "p14", group: "放大", text: "搅拌与散热能力评估", checked: false },
  { id: "p15", group: "放大", text: "加料速率与安全预案确认", checked: false },
];

/// 读出全部检查项；首次使用时用预设，之后用保存的数据
export function loadItems(): ChecklistItem[] {
  const saved = localStorage.getItem(KEY);
  if (saved === null) return PRESET.map((i) => ({ ...i })); // 深拷贝
  try {
    const arr = JSON.parse(saved);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

/// 保存全部检查项
export function saveItems(items: ChecklistItem[]): void {
  localStorage.setItem(KEY, JSON.stringify(items));
}

/// 新增一条自定义项（返回新项）
export function addItem(group: string, text: string): ChecklistItem {
  return {
    id: `c-${Date.now()}-${Math.floor(Math.random() * 10000)}`,
    group: group || "自定义",
    text,
    checked: false,
  };
}

/// 切换勾选状态
export function toggleItem(items: ChecklistItem[], id: string): ChecklistItem[] {
  return items.map((i) => (i.id === id ? { ...i, checked: !i.checked } : i));
}

/// 删除一条（自定义项可删；预设项删了也会从列表消失，下次初始化不再出现）
export function removeItem(items: ChecklistItem[], id: string): ChecklistItem[] {
  return items.filter((i) => i.id !== id);
}
