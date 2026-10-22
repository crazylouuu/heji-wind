<script setup lang="ts">
// ============================================================
// RecordsView.vue —— 记录页（底部 Tab：记录）→ 执行工作台
// Day6：计时器 + 检查清单
// Day7：曾加入"实验记录"面板（CRUD+拍照+导出）
// 【2026-09-23 变更】应需求停用实验记录入口（实验数据有泄露风险）：
//   - 前端隐藏"📝 实验记录"子 Tab 与面板
//   - 代码与数据库表保留，恢复时只需把本文件的子 Tab/面板加回
//   - Rust 命令（create_experiment 等）不删，前端不调用即无入口
// 布局：页内两个子 Tab（计时器 / 检查清单）
// ============================================================
import { ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
import TimerList from "../components/TimerList.vue";
import ChecklistPanel from "../components/ChecklistPanel.vue";

// 当前激活的子 Tab（实验记录已停用，只剩两个）
const activeTab = ref<"timers" | "checklist">("timers");
</script>

<template>
  <div class="records">
    <h1 class="title">执行工作台</h1>

    <!-- 页内子 Tab -->
    <div class="sub-tabs">
      <button class="sub-tab" :class="{ on: activeTab === 'timers' }" @click="activeTab = 'timers'">
        <AppIcon name="clock" />计时器
      </button>
      <button
        class="sub-tab"
        :class="{ on: activeTab === 'checklist' }"
        @click="activeTab = 'checklist'"
      >
        <AppIcon name="listChecks" />检查清单
      </button>
    </div>

    <section v-show="activeTab === 'timers'" class="panel">
      <TimerList />
    </section>

    <section v-show="activeTab === 'checklist'" class="panel">
      <ChecklistPanel />
    </section>
  </div>
</template>

<style scoped>
.records {
  max-width: 760px;
  margin: 0 auto;
}

.title {
  margin: 0 0 0.8rem;
  font-size: 1.3rem;
}

.sub-tabs {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.8rem;
}

.sub-tab {
  flex: 1;
  min-height: 44px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background-color: var(--card);
  color: var(--muted);
  font-size: 0.95rem;
  cursor: pointer;
}

/* 当前激活的子 Tab：主色底 */
.sub-tab.on {
  background-color: var(--primary-solid);
  color: #ffffff;
  border-color: var(--primary);
}

.panel {
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
}

/* 子 Tab 图标：与文字居中对齐（SVG 默认是行内基线对齐，会偏上） */
.sub-tab {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

</style>
