<script setup lang="ts">
// ============================================================
// CalculatorView.vue —— 计算器页（顶部 Tab：计算器）
// 5 个模块：浓度/稀释、产率、柱层析、单位换算、温度换算
// （投料计划表已于 2026-09-24 剥离为独立页面 FeedTableView.vue）
// 特性：
//   - 每个模块独立卡片，输入即算（computed 自动重算）
//   - 结果可"复制"、"保存到历史"（localStorage）
// 计算逻辑全部在 utils/calculator.ts（纯函数，可测试可复用）
// ============================================================
import { computed, ref } from "vue";
import * as calc from "../utils/calculator";
import { addHistory, getHistory } from "../utils/calcHistory";

// ---- Tab 切换 ----
// 【2026-09-24】投料计划表已剥离为独立页面（FeedTableView.vue），
// 计算器只保留其余 5 个模块
const activeTab = ref("dilution"); // 当前显示的模块 id
const tabs = [
  { id: "dilution", name: "浓度/稀释" },
  { id: "yield", name: "产率" },
  { id: "column", name: "柱层析" },
  { id: "units", name: "单位换算" },
  { id: "temp", name: "温度换算" },
];

// ---- 历史展开 ----
/// 点击历史项：展开/收起详情（显示完整摘要）
const openIndex = ref<number | null>(null); // 当前展开的历史下标
function toggleHistory(i: number) {
  openIndex.value = openIndex.value === i ? null : i;
}

// ---- 模块 2：浓度/稀释 ----
const dC1 = ref<number | null>(null); // 原液浓度
const dC2 = ref<number | null>(null); // 目标浓度
const dV2 = ref<number | null>(null); // 目标体积
const dilutionResult = computed(() => {
  const v1 = calc.calcDilution(dC1.value ?? 0, dC2.value ?? 0, dV2.value ?? 0);
  const add = calc.calcSolventToAdd(dV2.value ?? 0, v1);
  return { v1, add };
});

// ---- 模块 3：产率 ----
const yMass = ref<number | null>(null);  // 底物质量 g
const yMw = ref<number | null>(null);    // 底物分子量
const yProdMw = ref<number | null>(null);// 产物分子量
const yActual = ref<number | null>(null);// 实际产量 g
const yieldResult = computed(() => {
  const mmol = calc.calcMoles(yMass.value ?? 0, yMw.value ?? 0);
  const theo = calc.calcTheoreticalYield(mmol, yProdMw.value ?? 0);
  const pct = calc.calcYield(yActual.value ?? 0, theo);
  return { mmol, theo, pct };
});

// ---- 模块 4：柱层析梯度 ----
const gStart = ref<number | null>(null); // 起始 B%
const gEnd = ref<number | null>(null);   // 终点 B%
const gVol = ref<number | null>(null);   // 梯度体积 mL
const gAt = ref<number | null>(null);    // 询问某体积处 B%
const columnResult = computed(() => {
  const step = calc.calcGradientStep(gStart.value ?? 0, gEnd.value ?? 0, gVol.value ?? 0);
  const at = gAt.value !== null ? calc.calcGradientAt(gStart.value ?? 0, step, gAt.value) : null;
  return { step, at };
});

// ---- 模块 5：单位换算 ----
const uType = ref<"mass" | "volume" | "conc">("mass"); // 换算类型
const uValue = ref<number | null>(null);                // 基准数值
// 统一返回结构：primary=主单位数值，secondary=副单位数值，
// 避免 TS 联合类型访问属性报错
const unitsResult = computed(() => {
  const v = uValue.value ?? 0;
  if (uType.value === "mass") {
    const { mg, ug } = calc.massUnits(v);
    return { label: "g", primary: mg, primaryUnit: "mg", secondary: ug, secondaryUnit: "µg" };
  }
  if (uType.value === "volume") {
    const { ml, ul } = calc.volumeUnits(v);
    return { label: "L", primary: ml, primaryUnit: "mL", secondary: ul, secondaryUnit: "µL" };
  }
  const { mM, uM } = calc.concUnits(v);
  return { label: "mol/L", primary: mM, primaryUnit: "mM", secondary: uM, secondaryUnit: "µM" };
});

// ---- 模块 6：温度换算 ----
const tC = ref<number | null>(null); // 摄氏度
const tF = ref<number | null>(null); // 华氏度
const tK = ref<number | null>(null); // 开尔文
// 输入摄氏度时算另外两个
const tempFromC = computed(() => {
  if (tC.value === null) return null;
  return { f: calc.cToF(tC.value), k: calc.cToK(tC.value) };
});
// 输入华氏度时算另外两个
const tempFromF = computed(() => {
  if (tF.value === null) return null;
  return { c: calc.fToC(tF.value), k: calc.fToC(tF.value) + 273.15 };
});
// 输入开尔文时算另外两个
const tempFromK = computed(() => {
  if (tK.value === null) return null;
  return { c: calc.kToC(tK.value), f: calc.cToF(calc.kToC(tK.value)) };
});

// ---- 复制与历史 ----
const copied = ref(""); // 提示"已复制"

/// 复制文本到剪贴板（WebView 支持 Clipboard API）
async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    copied.value = "已复制 ✓";
    setTimeout(() => (copied.value = ""), 1500); // 1.5 秒后清除提示
  } catch {
    copied.value = "复制失败";
  }
}

/// 保存一条历史记录
function saveHistory(module: string, summary: string) {
  const now = new Date();
  const time = now.toTimeString().slice(0, 8); // "12:30:05"
  addHistory({ time, module, summary });
}

// 历史列表（响应式：保存后自动更新）
const history = ref(getHistory());
</script>

<template>
  <div class="calc">
    <h1 class="title">计算器</h1>

    <!-- 模块 Tab -->
    <div class="tabs">
      <button
        v-for="t in tabs"
        :key="t.id"
        class="tab-btn"
        :class="{ active: activeTab === t.id }"
        @click="activeTab = t.id"
      >
        {{ t.name }}
      </button>
    </div>

    <!-- ===== 模块 2：浓度/稀释 ===== -->
    <section v-show="activeTab === 'dilution'" class="card">
      <h2>浓度 / 稀释（C1·V1 = C2·V2）</h2>
      <label class="field">原液浓度 C1 (mol/L)
        <input type="number" v-model.number="dC1" placeholder="如 5.0" />
      </label>
      <label class="field">目标浓度 C2 (mol/L)
        <input type="number" v-model.number="dC2" placeholder="如 0.5" />
      </label>
      <label class="field">目标体积 V2 (mL)
        <input type="number" v-model.number="dV2" placeholder="如 100" />
      </label>
      <p class="result">
        取原液 <strong>{{ dilutionResult.v1.toFixed(2) }}</strong> mL，补溶剂
        <strong>{{ dilutionResult.add.toFixed(2) }}</strong> mL
      </p>
      <button class="act" @click="copyText(`取原液 ${dilutionResult.v1.toFixed(2)} mL 补至 ${dV2 ?? ''} mL`); saveHistory('浓度/稀释', `C1=${dC1 ?? ''}→C2=${dC2 ?? ''}，取原液 ${dilutionResult.v1.toFixed(2)} mL`)">复制结果</button>
    </section>

    <!-- ===== 模块 3：产率 ===== -->
    <section v-show="activeTab === 'yield'" class="card">
      <h2>产率</h2>
      <label class="field">限制试剂质量 (g)
        <input type="number" v-model.number="yMass" placeholder="如 0.500" />
      </label>
      <label class="field">限制试剂分子量 (g/mol)
        <input type="number" v-model.number="yMw" placeholder="如 122.12" />
      </label>
      <label class="field">产物分子量 (g/mol)
        <input type="number" v-model.number="yProdMw" placeholder="如 184.20" />
      </label>
      <label class="field">实际产量 (g)
        <input type="number" v-model.number="yActual" placeholder="如 0.310" />
      </label>
      <p class="result">
        限制试剂 = {{ yieldResult.mmol.toFixed(3) }} mmol<br />
        理论产量 = <strong>{{ yieldResult.theo.toFixed(3) }}</strong> g<br />
        产率 = <strong>{{ yieldResult.pct.toFixed(1) }}%</strong>
      </p>
      <button class="act" @click="saveHistory('产率', `产率 ${yieldResult.pct.toFixed(1)}%（理论 ${yieldResult.theo.toFixed(3)} g）`)">保存到历史</button>
    </section>

    <!-- ===== 模块 4：柱层析梯度 ===== -->
    <section v-show="activeTab === 'column'" class="card">
      <h2>柱层析梯度</h2>
      <label class="field">起始 B% （弱极性端）
        <input type="number" v-model.number="gStart" placeholder="如 5" />
      </label>
      <label class="field">终点 B%
        <input type="number" v-model.number="gEnd" placeholder="如 30" />
      </label>
      <label class="field">梯度体积 (mL)
        <input type="number" v-model.number="gVol" placeholder="如 300" />
      </label>
      <p class="result">
        每 mL 增加 <strong>{{ columnResult.step.toFixed(4) }}</strong> B%
      </p>
      <label class="field">询问某体积处 B%（mL）
        <input type="number" v-model.number="gAt" placeholder="如 150" />
      </label>
      <p class="result">
        {{ gAt ?? 0 }} mL 处 B% = <strong>{{ (columnResult.at ?? 0).toFixed(2) }}</strong>
      </p>
      <button class="act" @click="saveHistory('柱层析', `梯度 ${gStart ?? ''}%→${gEnd ?? ''}%（${gVol ?? ''} mL）`)">保存到历史</button>
    </section>

    <!-- ===== 模块 5：单位换算 ===== -->
    <section v-show="activeTab === 'units'" class="card">
      <h2>单位换算</h2>
      <div class="type-row">
        <button v-for="t in [['mass','质量'],['volume','体积'],['conc','浓度']]" :key="t[0]" class="type-btn" :class="{ active: uType === t[0] }" @click="uType = t[0] as any">{{ t[1] }}</button>
      </div>
      <label class="field">数值（{{ unitsResult.label }}）
        <input type="number" v-model.number="uValue" placeholder="如 1.5" />
      </label>
      <p class="result">
        {{ unitsResult.label }} → <strong>{{ unitsResult.primary.toFixed(3) }}</strong>
        {{ unitsResult.primaryUnit }} ｜
        <strong>{{ unitsResult.secondary.toFixed(3) }}</strong>
        {{ unitsResult.secondaryUnit }}
      </p>
      <button class="act" @click="saveHistory('单位换算', `${uValue ?? ''} ${unitsResult.label} → ${unitsResult.primary.toFixed(3)} ${unitsResult.primaryUnit} / ${unitsResult.secondary.toFixed(3)} ${unitsResult.secondaryUnit}`)">保存到历史</button>
    </section>

    <!-- ===== 模块 6：温度换算 ===== -->
    <section v-show="activeTab === 'temp'" class="card">
      <h2>温度换算</h2>
      <label class="field">摄氏 °C
        <input type="number" v-model.number="tC" placeholder="如 25" />
      </label>
      <p v-if="tempFromC" class="result">
        = <strong>{{ tempFromC.f.toFixed(1) }}</strong> °F ｜
        <strong>{{ tempFromC.k.toFixed(1) }}</strong> K
      </p>
      <div class="divider"></div>
      <label class="field">华氏 °F
        <input type="number" v-model.number="tF" placeholder="如 77" />
      </label>
      <p v-if="tempFromF" class="result">
        = <strong>{{ tempFromF.c.toFixed(1) }}</strong> °C ｜
        <strong>{{ tempFromF.k.toFixed(1) }}</strong> K
      </p>
      <div class="divider"></div>
      <label class="field">开尔文 K
        <input type="number" v-model.number="tK" placeholder="如 298.15" />
      </label>
      <p v-if="tempFromK" class="result">
        = <strong>{{ tempFromK.c.toFixed(1) }}</strong> °C ｜
        <strong>{{ tempFromK.f.toFixed(1) }}</strong> °F
      </p>
      <button class="act" @click="saveHistory('温度换算', `°C=${tC ?? ''} °F=${tF ?? ''} K=${tK ?? ''}`)">保存到历史</button>
    </section>

    <!-- 复制提示 -->
    <p v-if="copied" class="copied">{{ copied }}</p>

    <!-- ===== 历史记录 ===== -->
    <section class="card history">
      <h2>历史记录（最多 10 条，新纪录覆盖最旧）</h2>
      <ul v-if="history.length" class="history-list">
        <li v-for="(r, i) in history.slice(0, 10)" :key="i">
          <button class="h-row" :class="{ open: openIndex === i }" @click="toggleHistory(i)">
            <span class="h-time">{{ r.time }}</span>
            <span class="h-module">{{ r.module }}</span>
            <span class="h-summary">{{ r.summary.split("\n")[0] }}</span>
            <span class="h-arrow">{{ openIndex === i ? "▲" : "▼" }}</span>
          </button>
          <!-- 点击展开：显示完整内容（投料计划表 = 整张表格文本） -->
          <pre v-if="openIndex === i" class="h-detail">{{ r.summary }}</pre>
        </li>
      </ul>
      <p v-else class="hint">还没有历史记录，算完点"保存"</p>
    </section>
  </div>
</template>

<style scoped>
.calc {
  max-width: 760px;
  margin: 0 auto;
}

.title {
  margin: 0 0 0.8rem;
  font-size: 1.3rem;
}

/* 模块 Tab */
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.8rem;
}

.tab-btn {
  min-height: 40px;
  padding: 0.2rem 0.9rem;
  font-size: 0.9rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background-color: var(--card);
  color: var(--muted);
  cursor: pointer;
}

.tab-btn.active {
  background-color: var(--primary-solid);
  border-color: var(--primary);
  color: #ffffff;
}

/* 卡片 */
.card {
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  margin-bottom: 0.8rem;
}

.card h2 {
  margin: 0 0 0.8rem;
  font-size: 1.05rem;
}

/* 输入字段：标签在上，输入框在下 */
.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 0.6rem;
}

.field input {
  min-height: 44px;
  padding: 0.4rem 0.8rem;
  font-size: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--bg);
  color: var(--text);
}

.field input:focus {
  outline: none;
  border-color: var(--primary);
}

/* 结果 */
.result {
  font-size: 1rem;
  background-color: var(--primary-soft);
  border-radius: 8px;
  padding: 0.6rem 0.9rem;
  margin: 0.4rem 0 0.8rem;
  color: var(--text);
}

.result strong {
  color: var(--primary);
  font-size: 1.1rem;
}

.divider {
  border-top: 1px dashed var(--border);
  margin: 0.8rem 0;
}

/* 动作按钮 */
.act {
  min-height: 40px;
  padding: 0.3rem 1rem;
  border-radius: var(--radius-sm);
  border: none;
  background-color: var(--primary-solid);
  color: #ffffff;
  font-size: 0.9rem;
  cursor: pointer;
}

/* 类型切换（单位换算） */
.type-row {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.6rem;
}

.type-btn {
  min-height: 36px;
  padding: 0.2rem 0.8rem;
  font-size: 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--card);
  color: var(--muted);
  cursor: pointer;
}

.type-btn.active {
  background-color: var(--primary-solid);
  color: #ffffff;
}

.copied {
  color: var(--ok);
  font-size: 0.9rem;
  text-align: center;
}

/* 历史记录 */
.history-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.history-list li {
  padding: 0.2rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
}

/* 整行可点击（按钮占满宽度） */
.h-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  min-height: 40px;
  padding: 0.4rem;
  background: none;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  color: var(--text);
}

.h-row:hover,
.h-row.open {
  background-color: var(--primary-soft);
}

.h-time {
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.h-module {
  color: var(--primary);
  font-weight: 600;
}

/* 第一行摘要（截断显示），其余内容点击展开 */
.h-summary {
  color: var(--text);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.h-arrow {
  color: var(--muted);
}

/* 展开详情：保留换行/制表符的表格文本 */
.h-detail {
  margin: 0.3rem 0.4rem 0.5rem;
  padding: 0.6rem;
  border-radius: 8px;
  background-color: var(--bg);
  border: 1px solid var(--border);
  font-size: 0.8rem;
  white-space: pre;
  overflow-x: auto;
  color: var(--text);
}

.hint {
  color: var(--muted);
  text-align: center;
  font-size: 0.9rem;
}
</style>
