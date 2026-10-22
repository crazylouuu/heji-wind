<script setup lang="ts">
// ============================================================
// FeedTableView.vue —— 投料计划表（独立页面，顶部 Tab：投料表）
// 2026-09-24：从计算器页剥离，独立成页（用户需求：与计算器/SOP 并列）
// 规则：第一行 = 限制试剂（基准物料），默认 1.0 eq；
//       它的 MW 与投料量直接在第一行输入（投料量列可编辑）
// 其他行输入 MW 和 eq/w，投料量与 mmol 自动计算：
//   eq 模式：投料量(g) = 基准mmol × eq × 本行MW / 1000
//   w  模式：投料量(g) = 基准投料量 × 重量比
// 计算逻辑在 utils/calculator.ts（纯函数，可测试可复用）
// ============================================================
import { computed, ref, watch } from "vue";
import * as calc from "../utils/calculator";
import { addHistory, getHistory } from "../utils/calcHistory";

// ---- 投料表 ----
const baseMass = ref<number | null>(null); // 基准投料量 g（第一行"投料量"列输入）

// 前端行的类型（MW/当量允许留空，null 表示未填，计算时按 0）
interface FeedRowInput {
  name: string;
  mw: number | null;
  mode: "eq" | "w";
  value: number | null;
  note: string;
}

// 第一行固定 1.0 eq（限制试剂）；mode/value 不再改动
const rows = ref<FeedRowInput[]>([
  { name: "基准物料", mw: null, mode: "eq", value: 1, note: "限制试剂" },
  { name: "", mw: null, mode: "eq", value: 1.2, note: "" },
  { name: "", mw: null, mode: "eq", value: 2.0, note: "" },
]);

// 基准分子量 = 第一行的 MW（用户直接在第一行输入）
const baseMw = computed(() => rows.value[0]?.mw ?? 0);

// ---- 手动计算 ----
/// 计算结果（点击「计算」按钮后才生成；未计算为 null）
const results = ref<calc.FeedRowResult[] | null>(null);
const calculated = ref(false); // 是否已点过「计算」

/// 点击「计算」：按当前输入计算所有行的投料量与 mmol
function doCalc() {
  results.value = calc.calcFeedTable(
    baseMass.value ?? 0,
    baseMw.value,
    rows.value.map((r) => ({
      name: r.name,
      mw: r.mw ?? 0,
      mode: r.mode,
      value: r.value ?? 0,
      note: r.note,
    })),
  );
  calculated.value = true;
}

// 输入一旦变化，结果作废，必须重新点「计算」
// （deep: true = 监听 rows 数组里每个对象的字段变化）
watch(
  [rows, baseMass],
  () => {
    calculated.value = false;
  },
  { deep: true },
);

/// 加一行（默认 eq=1.0，用户自己改）
function addRow() {
  rows.value.push({ name: "", mw: null, mode: "eq", value: 1.0, note: "" });
  actuals.value.push(null); // 实称列同步加一行（空）
}

/// 删一行（基准行不可删）
function removeRow(i: number) {
  if (i === 0) return;
  rows.value.splice(i, 1);
  actuals.value.splice(i, 1); // 实称列同步删一行
}

// ---- 实称记录（2026-09-24 Day8 新增）----
/// 每行实际称量 g（null = 还没称）
const actuals = ref<(number | null)[]>(rows.value.map(() => null));

/// 实际基准投料量：基准行有实称用实称，否则退回计划投料量
const actualBase = computed(() => actuals.value[0] ?? baseMass.value ?? 0);

/// 每行实称结果（称完自动算）：实际 mmol + 实际 eq./w 文本
/// 实际 eq = 本行实称mmol ÷ 实际基准mmol（基准行恒为 1.0 eq）
/// 实际 w  = 本行实称g ÷ 实际基准投料量g
const actualRows = computed(() => {
  // 实际基准 mmol 由 calcActualRatio 内部计算，这里无需重复
  return rows.value.map((r, i) => {
    const g = actuals.value[i] ?? null;
    if (g === null) return null; // 没称 → 不显示
    const mmol = (r.mw ?? 0) > 0 ? (g / (r.mw ?? 0)) * 1000 : 0;
    if (i === 0) return { mmol, label: "1.0 eq（基准）" };
    const ratio = calc.calcActualRatio(
      actualBase.value,
      baseMw.value,
      r.mw ?? 0,
      r.mode,
      g,
    );
    const label = r.mode === "eq" ? `${ratio.toFixed(3)} eq` : `${ratio.toFixed(3)} w`;
    return { mmol, label };
  });
});

/// 清空全部实称
function clearActuals() {
  actuals.value = rows.value.map(() => null);
}

/// 保存整张投料表到历史（表格文本，可点击查看）
function saveFeedTable() {
  // 还没点「计算」就保存 → 提示，不保存
  if (!calculated.value || !results.value) {
    showTip("请先点击「计算」", false);
    return;
  }
  const head = "物料\tMW\teq./w\tmmol\t投料量(g)\t备注";
  const lines = rows.value.map((r, i) => {
    const res = results.value![i];
    const amt = res?.amountG ?? 0;
    const mmol = res?.mmol ?? 0;
    // 第一行固定显示 1.0 eq，其他行按实际模式与数值
    const label = i === 0 ? "1.0 eq" : r.mode === "eq" ? `${r.value ?? 0} eq` : `${r.value ?? 0} w`;
    return `${r.name || "（未命名）"}\t${r.mw ?? ""}\t${label}\t${mmol.toFixed(3)}\t${amt.toFixed(3)}\t${r.note}`;
  });
  // 保存完整表格文本（summary 支持换行，点击历史项可查看全文）
  saveHistory("投料计划", [head, ...lines].join("\n"));
  showTip("已保存 ✓", true);
}

// ---- 历史记录 ----
const savedTip = ref(""); // 提示（已保存 / 请先计算）
const tipOk = ref(true);  // 提示是成功(true)还是警告(false)

/// 显示提示：1.5 秒后自动消失
function showTip(text: string, ok: boolean) {
  savedTip.value = text;
  tipOk.value = ok;
  setTimeout(() => (savedTip.value = ""), 1500);
}
const openIndex = ref<number | null>(null); // 当前展开的历史下标

/// 点击历史项：展开/收起详情（显示完整摘要）
function toggleHistory(i: number) {
  openIndex.value = openIndex.value === i ? null : i;
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
  <div class="feed">
    <h1 class="title">投料计划表</h1>
    <p class="hint">
      第一行 = <b>限制试剂</b>（默认 1.0 eq），MW 和<b>投料量</b>直接在第一行输入；
      其他行填 MW 与 eq/w，点右下角<b>「计算」</b>后显示投料量与 mmol。
    </p>

    <!-- 投料表格 -->
    <section class="card">
      <table class="feed-table">
        <thead>
          <tr>
            <th>物料</th><th>MW</th><th>eq./w</th><th>mmol</th><th>投料量</th><th>备注</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="i" :class="{ base: i === 0 }">
            <td>
              <input v-model="row.name" :placeholder="i === 0 ? '限制试剂' : '物料名'" />
            </td>
            <td>
              <input type="number" v-model.number="row.mw" :placeholder="i === 0 ? '限制试剂 MW' : '分子量'" />
            </td>
            <td>
              <!-- 第一行：固定 1.0 eq（只读文本） -->
              <span v-if="i === 0" class="eq-fixed">1.0 eq</span>
              <!-- 其他行：eq/w 下拉 + 数值输入 -->
              <div v-else class="eqw">
                <select v-model="row.mode" title="eq=当量比，w=重量比">
                  <option value="eq">eq</option>
                  <option value="w">w</option>
                </select>
                <input type="number" v-model.number="row.value" placeholder="数值" />
              </div>
            </td>
            <!-- 毫摩尔数（点「计算」后显示，只读） -->
            <td class="amt mmol">{{ calculated ? (results?.[i]?.mmol ?? 0).toFixed(2) : "–" }}</td>
            <td class="amt">
              <!-- 第一行：投料量可输入（限制试剂投料量） -->
              <input
                v-if="i === 0"
                type="number"
                v-model.number="baseMass"
                class="amt-input"
                placeholder="投料量 g"
              />
              <!-- 其他行：点「计算」后显示（只读） -->
              <span v-else>{{ calculated ? (results?.[i]?.amountG ?? 0).toFixed(3) + " g" : "–" }}</span>
            </td>
            <td><input v-model="row.note" placeholder="备注" /></td>
            <td>
              <button v-if="i > 0" class="del" title="删除此行" @click="removeRow(i)">✕</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="feed-actions">
        <button class="act" @click="addRow">+ 加一行</button>
        <button class="act ghost" @click="saveFeedTable">保存</button>
        <span v-if="savedTip" class="saved-tip" :class="{ err: !tipOk }">{{ savedTip }}</span>
        <button class="act calc-btn" @click="doCalc">计算</button>
      </div>
    </section>

    <!-- ===== 实称记录（2026-09-24 Day8 新增）===== -->
    <section class="card actual-card">
      <h2>实称记录</h2>
      <p class="hint">
        称完实际重量填入下表，自动算<b>实际 mmol</b> 与<b>实际 eq./w</b>（相对基准行实称）。
        基准行不填实称时，按计划投料量作为基准。
      </p>
      <table class="feed-table">
        <thead>
          <tr>
            <th>物料</th><th>计划投料量(g)</th><th>实称(g)</th><th>实际 mmol</th><th>实际 eq./w</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="i" :class="{ base: i === 0 }">
            <td>{{ row.name || "（未命名）" }}</td>
            <td class="amt">{{ calculated ? (results?.[i]?.amountG ?? 0).toFixed(3) : "–" }}</td>
            <td>
              <input
                type="number"
                v-model.number="actuals[i]"
                class="amt-input"
                placeholder="实称 g"
              />
            </td>
            <td class="amt">{{ actualRows[i] ? actualRows[i]!.mmol.toFixed(2) : "–" }}</td>
            <td class="amt">{{ actualRows[i] ? actualRows[i]!.label : "–" }}</td>
          </tr>
        </tbody>
      </table>
      <div class="feed-actions">
        <button class="act ghost" @click="clearActuals">清空实称</button>
      </div>
    </section>

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
      <p v-else class="hint">还没有历史记录，保存投料表后在这里查看</p>
    </section>
  </div>
</template>

<style scoped>
.feed {
  max-width: 860px;
  margin: 0 auto;
}

.title {
  margin: 0 0 0.8rem;
  font-size: 1.3rem;
}

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

.hint {
  color: var(--muted);
  font-size: 0.9rem;
  margin: 0 0 0.8rem;
}

/* ---- 投料计划表 ---- */
.feed-table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.6rem 0;
  font-size: 0.85rem;
}

.feed-table th {
  text-align: left;
  padding: 0.4rem 0.3rem;
  color: var(--muted);
  border-bottom: 2px solid var(--border);
  font-weight: 600;
}

.feed-table td {
  padding: 0.3rem;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

/* 基准行高亮 */
.feed-table tr.base td {
  background-color: var(--primary-soft);
}

.feed-table input,
.feed-table select {
  width: 100%;
  min-height: 36px;
  padding: 0.2rem 0.5rem;
  font-size: 0.9rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background-color: var(--bg);
  color: var(--text);
  box-sizing: border-box;
}

.feed-table input:focus,
.feed-table select:focus {
  outline: none;
  border-color: var(--primary);
}

/* 第一行固定当量文本：主色加粗 */
.eq-fixed {
  display: inline-block;
  min-height: 36px;
  line-height: 36px;
  padding: 0 0.5rem;
  color: var(--primary);
  font-weight: 700;
}

/* 第一行投料量输入框 */
.amt-input {
  min-height: 36px;
  padding: 0.2rem 0.5rem;
  font-size: 0.9rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--primary);
  background-color: var(--bg);
  color: var(--primary);
  font-weight: 700;
  box-sizing: border-box;
}

/* eq/w：模式下拉 + 数值输入并排 */
.eqw {
  display: flex;
  gap: 0.3rem;
}

.eqw select {
  width: 3.2rem;
  flex-shrink: 0;
}

/* 投料量结果：主色加粗 */
.feed-table .amt {
  color: var(--primary);
  font-weight: 700;
  white-space: nowrap;
}

/* 删除行按钮 */
.del {
  min-height: 30px;
  width: 30px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: none;
  color: var(--danger);
  cursor: pointer;
}

.feed-actions {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

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

/* 次级按钮（保存） */
.act.ghost {
  background: none;
  border: 1px solid var(--primary);
  color: var(--primary);
}

/* 提示：成功为绿色，警告（如"请先计算"）为红色 */
.saved-tip {
  color: var(--ok);
  font-size: 0.9rem;
  line-height: 40px;
}

.saved-tip.err {
  color: var(--danger);
}

/* 计算按钮：推到操作行最右侧（右下角） */
.calc-btn {
  margin-left: auto;
}

/* ---- 历史记录 ---- */
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
</style>
