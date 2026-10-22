<script setup lang="ts">
// ============================================================
// SolventDetailView.vue —— 溶剂详情页
// 0.8.0 新增：列表页精简后，点行进来看全部数据——
//   分子式 / 沸点 / 密度 / 极性 / 与水混溶 / 闪点 /
//   管制与毒性（徽章）/ 危害提示 / 常见用途 / 除水干燥
// 路由：/solvents/:id（:id = CAS 号，唯一）
// 免责：参考值以试剂瓶标签、最新 SDS 与最新名录为准
// ============================================================
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { SOLVENTS, riskClass } from "../data/solvents";

const route = useRoute();
const router = useRouter();

/// 按 CAS 号（路由参数）找到这条溶剂
const sol = computed(() =>
  SOLVENTS.find((s) => s.cas === route.params.id),
);

/// 返回列表
function goBack() {
  router.push("/solvents");
}
</script>

<template>
  <div class="detail">
    <!-- 顶部：返回 + 标题 -->
    <div class="top">
      <button class="back" @click="goBack">‹ 返回</button>
    </div>

    <!-- 溶剂不存在时的兜底 -->
    <div v-if="!sol" class="not-found">
      <p>未找到该溶剂（可能已被移除）</p>
      <button class="back" @click="goBack">返回列表</button>
    </div>

    <template v-else>
      <h1 class="title">{{ sol.name }}</h1>

      <!-- 管制/毒性徽章（无管制显示"无"） -->
      <div class="risks">
        <span v-if="sol.risk.length === 0" class="no-risk">无管制/毒性标注</span>
        <span
          v-for="r in sol.risk"
          :key="r"
          class="risk-badge"
          :class="riskClass(r)"
        >{{ r }}</span>
      </div>

      <!-- 图例（解释三种颜色） -->
      <div class="legend">
        <span class="lg"><span class="risk-badge risk-yz">易制毒/易制爆</span> 受名录管制</span>
        <span class="lg"><span class="risk-badge risk-po">过氧化物易爆</span> 使用前检测</span>
        <span class="lg"><span class="risk-badge risk-tox">有毒</span> 注意防护</span>
      </div>

      <!-- 物性明细表：英文名·CAS 与沸点/密度等全部数据统一放表格 -->
      <table class="kv">
        <tbody>
          <tr><td>英文名/分子式</td><td>{{ sol.en }} · {{ sol.formula }}</td></tr>
          <tr><td>CAS</td><td>{{ sol.cas }}</td></tr>
          <tr><td>沸点</td><td>{{ sol.bp ?? "—" }} °C（常压）</td></tr>
          <tr><td>密度</td><td>{{ sol.density !== null ? sol.density.toFixed(3) : "—" }} g/mL（20°C）</td></tr>
          <tr><td>极性</td><td>{{ sol.polarity }}（介电常数 ε {{ sol.dielectric ?? "—" }}）</td></tr>
          <tr><td>与水混溶</td><td>{{ sol.solubility }}</td></tr>
          <tr><td>闪点</td><td>{{ sol.flash ?? "—（不易燃/无闪点）" }} °C</td></tr>
          <tr><td>常见用途</td><td>{{ sol.use }}</td></tr>
          <tr><td>除水/干燥</td><td>{{ sol.desiccant }}</td></tr>
          <tr class="hazard-row"><td>危害提示</td><td class="hazard">{{ sol.hazard }}</td></tr>
        </tbody>
      </table>

      <!-- 法规提示 -->
      <p class="law">
        本页数据为参考值，以<b>试剂瓶标签、最新 SDS</b>与最新版
        《易制毒化学品管理条例》《易制爆危险化学品名录》为准。
        涉及管制化学品的购买与使用须遵守当地法规。
      </p>
    </template>
  </div>
</template>

<style scoped>
.detail {
  max-width: 640px;
  margin: 0 auto;
  padding: 0 0.5rem;
}

.top {
  margin-bottom: 0.6rem;
}

.back {
  min-height: 40px;
  padding: 0.3rem 1rem;
  font-size: 0.95rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--card);
  color: var(--text);
  cursor: pointer;
}

.back:active {
  background-color: var(--border);
}

.title {
  margin: 0 0 0.4rem;
  font-size: 1.5rem;
}

/* ---- 管制徽章 ---- */
.risks {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.no-risk {
  color: var(--muted);
  font-size: 0.85rem;
}

.risk-badge {
  display: inline-block;
  padding: 0.1rem 0.6rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}

.risk-yz { background-color: var(--danger); color: #ffffff; }
.risk-po { background-color: #7c3aed; color: #ffffff; }
.risk-tox { background-color: #d97706; color: #ffffff; }

/* 图例 */
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 0.8rem;
  font-size: 0.78rem;
  color: var(--muted);
  margin-bottom: 0.8rem;
}

.lg {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

/* ---- 明细表 ---- */
.kv {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.kv td {
  padding: 0.55rem 0.7rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}

.kv td:first-child {
  width: 30%;
  color: var(--muted);
  white-space: nowrap;
}

.hazard-row td:last-child {
  color: var(--danger);
}

/* 法规提示 */
.law {
  font-size: 0.78rem;
  color: var(--danger);
  background-color: var(--danger-soft);
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
  margin: 0.8rem 0 0;
  line-height: 1.5;
}

.not-found {
  text-align: center;
  padding: 2rem 0;
  color: var(--muted);
}
</style>
