<script setup lang="ts">
// ============================================================
// SolventView.vue —— 溶剂查询（列表页）
// 2026-09-24 新增：内置常用溶剂物性 + 搜索
// 2026-09-24 0.7.0：扩充至 86 种 + CAS + 管制标注
// 2026-09-24 0.8.0：手机界面精简——
//   列表只显示 中文名/英文名/CAS/沸点/密度，
//   其余数据（极性/混溶/闪点/管制/危害/用途/干燥）点进详情页看。
// 数据在 src/data/solvents.ts（纯数据文件，与页面分离）
// 免责：参考值以试剂瓶标签、最新 SDS 与最新名录为准
// ============================================================
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { SOLVENTS, searchSolvents, riskClass } from "../data/solvents";

const router = useRouter(); // 路由实例（跳详情页用）
const keyword = ref(""); // 搜索关键词
const list = computed(() => searchSolvents(keyword.value));

/// 点击一行 → 跳到该溶剂详情页（用 CAS 号作地址，唯一）
function goDetail(cas: string) {
  router.push(`/solvents/${cas}`);
}
</script>

<template>
  <div class="solv">
    <h1 class="title">溶剂查询</h1>
    <p class="hint">
      共 {{ SOLVENTS.length }} 种常用溶剂，点行查看详情。
      实际使用请以<b>试剂瓶标签与最新 SDS</b>为准。
    </p>
    <p class="law">
      ⚠️ 易制毒/易制爆溶剂购买使用须遵守当地备案/审批要求（见详情页标注）。
    </p>

    <!-- 搜索框 -->
    <label class="field">搜索（中文名 / 英文 / CAS / 分子式 / 用途）
      <input v-model="keyword" placeholder="如：THF、甲醇、67-56-1、萃取" />
    </label>

    <!-- 精简列表：大点击区卡片行，手机友好 -->
    <div class="list">
      <button
        v-for="s in list"
        :key="s.cas"
        class="row"
        @click="goDetail(s.cas)"
      >
        <span class="name-line">
          <span class="name">{{ s.name }}</span>
          <!-- 管制/毒性徽章：红=易制毒/易制爆，紫=过氧化物，橙=有毒 -->
          <span
            v-for="r in s.risk"
            :key="r"
            class="risk-badge"
            :class="riskClass(r)"
          >{{ r }}</span>
        </span>
        <span class="en">{{ s.en }} · CAS {{ s.cas }}</span>
        <span class="nums">
          <span class="num">沸点 {{ s.bp ?? "—" }} °C</span>
          <span class="num">密度 {{ s.density !== null ? s.density.toFixed(3) : "—" }} g/mL</span>
        </span>
        <span class="arrow">›</span>
      </button>
      <p v-if="list.length === 0" class="empty">没有匹配的溶剂，换个关键词试试</p>
    </div>
  </div>
</template>

<style scoped>
.solv {
  max-width: 640px; /* 手机友好宽度，桌面也不显得太宽 */
  margin: 0 auto;
  padding: 0 0.5rem;
}

.title {
  margin: 0 0 0.6rem;
  font-size: 1.3rem;
}

.hint {
  color: var(--muted);
  font-size: 0.9rem;
  margin: 0 0 0.4rem;
}

/* 法规提示：醒目但不刺眼（列表页只保留一行，详情页有完整图例） */
.law {
  font-size: 0.78rem;
  color: var(--danger);
  background-color: var(--danger-soft);
  border-radius: 8px;
  padding: 0.4rem 0.7rem;
  margin: 0 0 0.8rem;
  line-height: 1.4;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 0.8rem;
}

.field input {
  min-height: 44px;
  padding: 0.4rem 0.8rem;
  font-size: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--card);
  color: var(--text);
}

.field input:focus {
  outline: none;
  border-color: var(--primary);
}

/* ---- 卡片行列表 ---- */
.list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

/* 整行是按钮（大点击区，手机友好）；文字左对齐 */
.row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.15rem 0.6rem;
  text-align: left;
  min-height: 56px;
  padding: 0.5rem 0.8rem;
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 0.9rem;
  cursor: pointer;
}

.row:active {
  background-color: var(--border); /* 按下反馈（手机） */
}

.name {
  font-weight: 600;
  font-size: 1rem;
  margin-right: auto;
}

/* 名字 + 徽章同一行（可换行） */
.name-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem;
  width: 100%;
}

/* 管制/毒性徽章（列表行内，小号） */
.risk-badge {
  display: inline-block;
  padding: 0.05rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
}

.risk-yz { background-color: var(--danger); color: #ffffff; }
.risk-po { background-color: #7c3aed; color: #ffffff; }
.risk-tox { background-color: #d97706; color: #ffffff; }

.en {
  color: var(--muted);
  font-size: 0.75rem;
  width: 100%; /* 换行占满一行，手机上也清晰 */
}

.nums {
  display: flex;
  gap: 0.6rem;
  font-size: 0.8rem;
  color: var(--text);
}

.num {
  background-color: var(--primary-soft);
  color: var(--primary);
  border-radius: 999px;
  padding: 0.05rem 0.5rem;
  white-space: nowrap;
}

.arrow {
  color: var(--muted);
  font-size: 1.2rem;
  margin-left: auto;
}

.empty {
  color: var(--muted);
  text-align: center;
  padding: 1rem;
}
</style>
