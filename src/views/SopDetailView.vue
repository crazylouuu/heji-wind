<script setup lang="ts">
// ============================================================
// SopDetailView.vue —— SOP 详情页（/sops/:id）
// 职责：
//   1. 按路由参数 id 从仓库找到这条 SOP
//   2. 提取"步骤"渲染成可勾选 checkbox（状态存 localStorage）
//   3. 渲染正文（marked 生成的 HTML）
// 数据流：路由 id → 仓库取数据 → 步骤解析 → 勾选状态读写
// ============================================================
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useSopsStore } from "../stores/sops";
import { extractSteps } from "../utils/sopSteps";
import { getStepChecks, setStepCheck } from "../utils/stepChecklist";
import { isFavorite, toggleFavorite } from "../utils/favorites";
import { resolveBodyImages } from "../utils/sopImages";

const route = useRoute();
const router = useRouter();
const store = useSopsStore();

// 页面进入时确保数据已加载
onMounted(() => {
  store.fetchAll();
});

// 当前 SOP：按路由参数 id 查找（computed：id 变了自动重新算）
const sop = computed(() => store.byId(String(route.params.id)));

// 步骤列表（从正文提取）
const steps = computed(() => (sop.value ? extractSteps(sop.value.bodyMd) : []));

// 勾选状态：响应式副本 { 步骤编号: 是否勾选 }
const checks = ref<Record<number, boolean>>({});

// ---- Day4：收藏 ----
// 重要：fav 必须声明在 watch 之前 —— watch 的 immediate 回调在 setup 执行到
// watch 那一行时立即同步运行并访问 fav；若 fav 声明在后面，会触发
// "暂时性死区(TDZ)" ReferenceError，导致整个组件渲染失败（页面白屏）。
const fav = ref(false); // 当前 SOP 是否已收藏

// 正文 HTML（图片相对路径已转成 Tauri 可加载 URL；必须声明在 watch 前，
// 因为 immediate 回调会同步写入它 —— 与 fav 同理，防 TDZ）
const bodyHtml = ref("");

// 已勾选数量（进度显示用）
const checkedCount = computed(
  () => Object.values(checks.value).filter(Boolean).length,
);

// 是否全部完成（用于提示）
const allDone = computed(
  () => steps.value.length > 0 && checkedCount.value === steps.value.length,
);

// 监听 SOP 变化：一旦拿到数据，从 localStorage 读回勾选状态和收藏状态
watch(
  sop,
  async (s) => {
    if (s) {
      checks.value = getStepChecks(s.meta.id);
      fav.value = isFavorite(s.meta.id);
      // 正文里的插图：相对路径 → 本地资源 URL（await：需要问 Rust 拿根目录）
      bodyHtml.value = await resolveBodyImages(s.bodyHtml, s.fileName);
    } else {
      checks.value = {};
      fav.value = false;
      bodyHtml.value = "";
    }
  },
  { immediate: true },
);

// 切换收藏：更新界面 + 写入 localStorage
function toggleFav() {
  if (!sop.value) return;
  fav.value = toggleFavorite(sop.value.meta.id);
}

// 切换勾选：更新内存 + 写入 localStorage
function toggleStep(stepIndex: number, checked: boolean) {
  checks.value[stepIndex] = checked;          // 1. 更新界面
  if (sop.value) {
    setStepCheck(sop.value.meta.id, stepIndex, checked); // 2. 存本地
  }
}

// 风险等级 → 提示文案（详情页警示）
function riskHint(risk: string): string {
  if (risk === "high" || risk === "critical") {
    return "高风险操作：请确认已阅读免责声明，并做好防护准备。";
  }
  return "";
}
</script>

<template>
  <div class="detail">
    <!-- 返回按钮 -->
    <button class="back" @click="router.push('/sops')">← 返回 SOP 列表</button>

    <!-- 加载中 / 未找到 -->
    <p v-if="store.loading" class="hint">加载中…</p>
    <p v-else-if="!sop" class="hint">未找到该 SOP（可能已被删除）</p>

    <template v-else>
      <!-- 头部：标题 + 收藏按钮 -->
      <div class="title-row">
        <h1 class="title">{{ sop.meta.title }}</h1>
        <button class="fav-btn" :class="{ faved: fav }" @click="toggleFav">
          {{ fav ? "★ 已收藏" : "☆ 收藏" }}
        </button>
      </div>
      <div class="meta-row">
        <span class="badge">{{ sop.meta.category }}</span>
        <span class="badge risk">{{ sop.meta.risk }}</span>
        <span v-for="t in sop.meta.tags" :key="t" class="badge tag">{{ t }}</span>
      </div>
      <div v-if="sop.meta.scale || sop.meta.temperature || sop.meta.time" class="meta-line">
        <span v-if="sop.meta.scale">规模：{{ sop.meta.scale }}</span>
        <span v-if="sop.meta.temperature">温度：{{ sop.meta.temperature }}</span>
        <span v-if="sop.meta.time">时长：{{ sop.meta.time }}</span>
      </div>

      <!-- 高风险警示 -->
      <div v-if="riskHint(sop.meta.risk)" class="warn-box">
        ⚠️ {{ riskHint(sop.meta.risk) }}
      </div>

      <!-- 步骤勾选区 -->
      <section v-if="steps.length > 0" class="steps-card">
        <div class="steps-head">
          <h2>步骤</h2>
          <span class="progress">已完成 {{ checkedCount }} / {{ steps.length }}</span>
        </div>
        <!-- 进度条：已完成比例 -->
        <div class="progress-bar">
          <div
            class="progress-fill"
            :style="{ width: steps.length ? (checkedCount / steps.length) * 100 + '%' : '0%' }"
          ></div>
        </div>
        <p v-if="allDone" class="all-done">✅ 全部步骤已完成，干得漂亮！</p>

        <!-- 每个步骤一个可勾选项（大点击区域，手套友好） -->
        <label v-for="step in steps" :key="step.index" class="step-item" :class="{ done: checks[step.index] }">
          <input
            type="checkbox"
            class="step-check"
            :checked="!!checks[step.index]"
            @change="(e) => toggleStep(step.index, (e.target as HTMLInputElement).checked)"
          />
          <span class="step-no">{{ step.index }}</span>
          <span class="step-text">{{ step.text }}</span>
        </label>
      </section>

      <!-- 正文渲染（marked 生成的 HTML） -->
      <section class="body-card">
        <!-- v-html：把 HTML 字符串渲染成真实界面。
             安全说明：内容来自用户自己 assets/sops 的本地文件，可信。
             bodyHtml 是转换后的版本（插图相对路径已解析成可加载 URL） -->
        <div class="sop-body" v-html="bodyHtml"></div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.detail {
  max-width: 760px;
  margin: 0 auto;
}

.back {
  background: none;
  border: none;
  color: var(--primary);
  font-size: 0.95rem;
  padding: 0.3rem 0;
  cursor: pointer;
  min-height: 36px;
}

.hint {
  color: var(--muted);
  text-align: center;
  padding: 2rem 0;
}

.title {
  margin: 0.3rem 0 0.6rem;
  font-size: 1.35rem;
}

/* 标题行：标题 + 收藏按钮并排 */
.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.fav-btn {
  min-height: 36px;
  padding: 0.2rem 0.8rem;
  font-size: 0.9rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background-color: var(--card);
  color: var(--muted);
  cursor: pointer;
  white-space: nowrap;
}

.fav-btn.faved {
  background-color: #fef3c7;
  border-color: #f59e0b;
  color: #b45309;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.badge {
  font-size: 0.75rem;
  padding: 0.1rem 0.6rem;
  border-radius: 999px;
  background-color: var(--primary-soft);
  color: var(--primary);
}
.badge.risk { background-color: var(--danger-soft); color: var(--danger); }
.badge.tag  { background-color: var(--card); color: var(--muted); border: 1px solid var(--border); }

.meta-line {
  margin-top: 0.5rem;
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.85rem;
  color: var(--muted);
}

/* 高风险警示框 */
.warn-box {
  margin-top: 0.8rem;
  padding: 0.7rem 1rem;
  border-radius: var(--radius-sm);
  background-color: var(--danger-soft);
  color: var(--danger);
  font-size: 0.9rem;
  border: 1px solid var(--danger);
}

/* 步骤卡片 */
.steps-card,
.body-card {
  margin-top: 1rem;
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
}

.steps-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.steps-head h2 {
  margin: 0;
  font-size: 1.05rem;
}

.progress {
  font-size: 0.85rem;
  color: var(--muted);
}

/* 进度条 */
.progress-bar {
  margin-top: 0.5rem;
  height: 8px;
  border-radius: 999px;
  background-color: var(--border);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: var(--ok);
  transition: width 0.2s ease;
}

.all-done {
  color: var(--ok);
  font-weight: 600;
  margin: 0.5rem 0 0;
}

/* 步骤项：整行可点击（label 包裹 input），完成态划线 */
.step-item {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.7rem 0.4rem;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  min-height: 44px;
}

.step-item:last-child {
  border-bottom: none;
}

.step-check {
  width: 20px;
  height: 20px;
  margin-top: 3px;
  accent-color: var(--ok); /* 勾选框颜色跟随主题 */
}

.step-no {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--primary);
  min-width: 1.4rem;
}

.step-text {
  flex: 1;
}

/* 勾选后：文字划线变灰 */
.step-item.done .step-text {
  text-decoration: line-through;
  color: var(--muted);
}

/* 正文区：标题与表格的间距美化 */
.sop-body h2 {
  font-size: 1.1rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.3rem;
}

.sop-body table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.sop-body th,
.sop-body td {
  border: 1px solid var(--border);
  padding: 0.4rem 0.6rem;
  text-align: left;
}

/* SOP 插图：限制最大宽度防止溢出，加边框和圆角更像"图" */
.sop-body img {
  max-width: 100%;
  height: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin: 0.6rem 0;
}
</style>
