// ============================================================
// calculator.ts —— 化学计算纯函数库（Day 5）
// 原则：只做"输入数字 → 输出数字"的纯函数，不碰界面。
// 好处：逻辑与界面解耦，可以单独测试；鸿蒙移植直接复用。
// 注意：这是通用化学计算（摩尔/稀释/产率等），
//       不包含任何具体化合物的合成指导。
// ============================================================

// ---------- 1. 摩尔 / 当量 ----------

/// 质量(g) + 分子量(g/mol) → 毫摩尔数(mmol)
export function calcMoles(massG: number, mw: number): number {
  if (mw === 0) return 0; // 除零保护
  return (massG / mw) * 1000;
}

/// 底物毫摩尔 × 当量数 → 所需试剂毫摩尔
export function calcEquiv(substrateMmol: number, equiv: number): number {
  return substrateMmol * equiv;
}

// ---------- 7. 投料计划表（Day 后处理 新增）----------

/// 当量模式：eq（当量比）或 w（重量比）
export type FeedMode = "eq" | "w";

/// 投料表一行（前端表格直接使用该结构）
export interface FeedRow {
  name: string;        // 物料名
  mw: number;          // 分子量 g/mol
  mode: FeedMode;      // eq=按当量算投料量；w=按重量比算投料量
  value: number;       // eq 的数值（如 1.2）或 w 的数值（如 0.5）
  note: string;        // 备注（限制试剂等）
}

/// 投料表每行的计算结果（投料量 + 毫摩尔数）
export interface FeedRowResult {
  amountG: number; // 投料量 g
  mmol: number;    // 毫摩尔数（mmol）
}

/// 计算整张投料表每行的投料量（g）与摩尔数（mmol）
/// 规则：第一行为基准物料（限制试剂），投料量 = baseMassG（用户输入）
/// eq 模式：mmol = 基准mmol × eq；投料量(g) = mmol × 本行MW / 1000
/// w  模式：投料量(g) = 基准投料量 × 重量比；mmol = 投料量 ÷ 本行MW × 1000
/// 所有行相互独立，改任一输入只影响该行（基准投料量影响所有行）
export function calcFeedTable(
  baseMassG: number,
  baseMw: number,
  rows: FeedRow[],
): FeedRowResult[] {
  // 基准毫摩尔：基准投料量(g) ÷ 基准分子量 × 1000 → mmol
  const baseMmol = baseMw > 0 ? (baseMassG / baseMw) * 1000 : 0;
  return rows.map((r, i) => {
    if (i === 0) return { amountG: baseMassG, mmol: baseMmol }; // 基准行
    if (r.mode === "w") {
      // 重量比：先算投料量，再反推毫摩尔
      const amountG = baseMassG * r.value;
      return { amountG, mmol: r.mw > 0 ? (amountG / r.mw) * 1000 : 0 };
    }
    // 当量：先算毫摩尔（基准mmol × eq），再推投料量
    const mmol = baseMmol * r.value;
    return { amountG: (mmol * r.mw) / 1000, mmol };
  });
}

/// 反向计算（相互验证）：已知某行实际称量(g)，反算实际当量或重量比
/// eq 模式：实际 eq = 实际mmol ÷ 基准mmol
/// w  模式：实际 w = 实际称量 ÷ 基准投料量
export function calcActualRatio(
  baseMassG: number,
  baseMw: number,
  mw: number,
  mode: FeedMode,
  actualG: number,
): number {
  if (mode === "eq") {
    const baseMmol = baseMw > 0 ? (baseMassG / baseMw) * 1000 : 0;
    if (baseMmol === 0 || mw === 0) return 0;
    return (actualG / mw) * 1000 / baseMmol; // 实际 mmol ÷ 基准 mmol
  }
  return baseMassG > 0 ? actualG / baseMassG : 0; // 实际重量比
}

// ---------- 2. 浓度 / 稀释（C1·V1 = C2·V2）----------

/// 稀释公式：已知原液浓度 C1、目标浓度 C2、目标体积 V2，
/// 返回需要取的原液体积 V1（mL），补到 V2 就是目标浓度
export function calcDilution(c1: number, c2: number, v2: number): number {
  if (c1 === 0) return 0; // 除零保护
  return (c2 * v2) / c1;
}

/// 需要补加的溶剂体积 = 目标体积 - 原液体积
export function calcSolventToAdd(v2: number, v1: number): number {
  return Math.max(0, v2 - v1);
}

// ---------- 3. 产率 ----------

/// 理论产量(g)：限制试剂毫摩尔 × 产物分子量 / 1000
export function calcTheoreticalYield(substrateMmol: number, productMw: number): number {
  return (substrateMmol * productMw) / 1000;
}

/// 产率(%)：实际产量 / 理论产量 × 100
export function calcYield(actualG: number, theoreticalG: number): number {
  if (theoreticalG === 0) return 0; // 除零保护
  return (actualG / theoreticalG) * 100;
}

// ---------- 4. 柱层析梯度 ----------

/// 梯度斜率：从起点 B% 到终点 B%，每毫升洗脱液增加多少 B%
/// （正值 = 极性逐渐升高）
export function calcGradientStep(startB: number, endB: number, volumeMl: number): number {
  if (volumeMl === 0) return 0;
  return (endB - startB) / volumeMl;
}

/// 某一体积处对应的 B%（线性梯度）
export function calcGradientAt(startB: number, step: number, volumeMl: number): number {
  return startB + step * volumeMl;
}

// ---------- 5. 单位换算 ----------

/// 质量：g → mg / µg
export function massUnits(g: number): { mg: number; ug: number } {
  return { mg: g * 1000, ug: g * 1_000_000 };
}

/// 体积：L → mL / µL
export function volumeUnits(l: number): { ml: number; ul: number } {
  return { ml: l * 1000, ul: l * 1_000_000 };
}

/// 浓度：mol/L → mmol/L(mM) / µmol/L(µM)
export function concUnits(molPerL: number): { mM: number; uM: number } {
  return { mM: molPerL * 1000, uM: molPerL * 1_000_000 };
}

// ---------- 6. 温度换算 ----------

/// °C → °F
export function cToF(c: number): number {
  return (c * 9) / 5 + 32;
}

/// °C → K
export function cToK(c: number): number {
  return c + 273.15;
}

/// °F → °C
export function fToC(f: number): number {
  return ((f - 32) * 5) / 9;
}

/// K → °C
export function kToC(k: number): number {
  return k - 273.15;
}
