<script setup lang="ts">
// ============================================================
// HomeView.vue —— 工作台（首页）
//
// P4 统一信息架构后的定位：整个应用的工作台，
// 上面是功能入口聚合，下面是「最近在做什么」的三块内容：
//   · 近期实验（来自后端，P3 已把后端并入主壳）
//   · 最近 SOP（本地资源）
//   · 我的收藏（本地）
//
// 原来这里只有 7 张入口卡片 + 收藏列表；现在补上后端数据，
// 让「工作台」名副其实 —— 一个页面看清最近状态 + 常用入口。
// ============================================================
import { computed, onMounted, ref } from "vue";
import AppIcon, { type IconName } from "../components/AppIcon.vue";
import { useRouter } from "vue-router";
import { useSopsStore } from "../stores/sops";
import { getFavorites } from "../utils/favorites";
import { apiGet, getBackendStatus, type BackendStatus } from "../utils/backend";

const router = useRouter();
const store = useSopsStore();

/** 后端状态（顶部状态条） */
const be = ref<BackendStatus | null>(null);

/** 近期实验（后端） */
interface ExpBrief {
  id: number;
  title: string;
  status: string;
  updated_at: string;
}
const recentExps = ref<ExpBrief[]>([]);
const expErr = ref("");

/** 后端状态文案 */
const statusText = computed(() => {
  if (!be.value) return "检测中…";
  if (be.value.running) return "实验记录服务已连接";
  return be.value.error || "实验记录服务未就绪";
});

/** 状态色（用于小圆点） */
const statusOk = computed(() => !!be.value?.running);

// 功能入口（按方案：6 个高频入口）
const entries: { title: string; desc: string; to: string; icon: IconName }[] = [
  { title: "新建实验", desc: "记录反应过程、投料与结果", to: "/lab", icon: "notebook" },
  { title: "查 SOP", desc: "反应类型与通用操作的标准流程", to: "/sops", icon: "book" },
  { title: "投料计算", desc: "MW/当量/重量比，自动算投料量", to: "/feed-table", icon: "scale" },
  { title: "溶剂查询", desc: "沸点、密度、极性、干燥方式", to: "/solvents", icon: "flask" },
  { title: "纯化操作", desc: "重结晶、柱层析、蒸馏、萃取要点", to: "/purify", icon: "funnel" },
  { title: "安全应急", desc: "泄漏、溅到、着火、废弃物处置", to: "/safety", icon: "shield" },
];

/** 次级入口（不占卡片位，排在下方一行） */
const minorEntries = [
  { title: "计算器", to: "/calculator" },
  { title: "计时器与清单", to: "/records" },
  { title: "设置与备份", to: "/mine" },
];

// 收藏的 SOP 列表（按 localStorage 里的 id 顺序展示）
const favSops = computed(() => {
  const ids = getFavorites();
  return ids
    .map((id) => store.byId(id))
    .filter((s): s is NonNullable<typeof s> => s !== undefined);
});

/** 最近打开的 SOP（取前 5 个） */
const recentSops = computed(() => store.sops.slice(0, 5));

async function loadBackend() {
  be.value = await getBackendStatus(true);
  if (!be.value.running) {
    expErr.value = be.value.error || "后端未就绪";
    return;
  }
  try {
    const res = await apiGet<{ experiments: ExpBrief[] }>("/api/experiments?limit=5");
    recentExps.value = res.experiments || [];
    expErr.value = "";
  } catch (e) {
    expErr.value = String(e);
  }
}

onMounted(async () => {
  store.fetchAll();
  await loadBackend();
});
</script>

<template>
  <div class="home">
    <!-- 顶部：品牌 + 后端状态 -->
    <div class="hero">
      <h1 class="brand">合记 ChemLab</h1>
      <p class="slogan">查 SOP → 算量 → 看安全 → 执行 → 计时 → 记录 → 复盘</p>
      <div class="status-line" :class="statusOk ? 'ok' : 'bad'" @click="loadBackend">
        <span class="dot"></span>
        {{ statusText }}
      </div>
    </div>

    <!-- 功能入口卡片 -->
    <div class="entry-grid">
      <button
        v-for="e in entries"
        :key="e.to"
        class="entry-card"
        @click="router.push(e.to)"
      >
        <span class="entry-icon"><AppIcon :name="e.icon" /></span>
        <span class="entry-title">{{ e.title }}</span>
        <span class="entry-desc">{{ e.desc }}</span>
      </button>
    </div>

    <!-- 次级入口 -->
    <div class="minor-row">
      <button v-for="m in minorEntries" :key="m.to" class="minor-chip" @click="router.push(m.to)">
        {{ m.title }}
      </button>
    </div>

    <!-- 近期实验（后端） -->
    <section class="fav-section">
      <h2 class="fav-title">近期实验</h2>

      <p v-if="expErr" class="fav-empty">
        {{ expErr }}<br />可在「设置 → 后端服务」查看状态或重启
      </p>
      <p v-else-if="!recentExps.length" class="fav-empty">
        还没有实验记录。<br />去「实验记录」新建一条
      </p>
      <button
        v-for="e in recentExps"
        :key="e.id"
        class="fav-card"
        @click="router.push('/lab')"
      >
        <span class="fav-name">{{ e.title || "未命名实验" }}</span>
        <span class="fav-cat">{{ e.status }} · {{ (e.updated_at || "").slice(0, 10) }}</span>
      </button>
    </section>

    <!-- 最近 SOP -->
    <section class="fav-section">
      <h2 class="fav-title">SOP 库</h2>
      <p v-if="!store.loading && recentSops.length === 0" class="fav-empty">SOP 资源尚未加载</p>
      <button
        v-for="sop in recentSops"
        :key="sop.meta.id"
        class="fav-card"
        @click="router.push(`/sops/${sop.meta.id}`)"
      >
        <span class="fav-name">{{ sop.meta.title }}</span>
        <span class="fav-cat">{{ sop.meta.category }}</span>
      </button>
    </section>

    <!-- 我的收藏 -->
    <section class="fav-section">
      <h2 class="fav-title">我的收藏</h2>

      <p v-if="!store.loading && favSops.length === 0" class="fav-empty">
        还没有收藏。<br />去 SOP 详情页点"☆ 收藏"添加
      </p>

      <button
        v-for="sop in favSops"
        :key="sop.meta.id"
        class="fav-card"
        @click="router.push(`/sops/${sop.meta.id}`)"
      >
        <span class="fav-name">{{ sop.meta.title }}</span>
        <span class="fav-cat">{{ sop.meta.category }}</span>
      </button>
    </section>

    <p class="footnote">内容完全本地存储，离线可用</p>
  </div>
</template>

<style scoped>
.home {
  max-width: 860px;
  margin: 0 auto;
}

.hero {
  text-align: center;
  padding: 1.2rem 0 0.8rem;
}

.brand {
  margin: 0;
  font-size: 1.6rem;
}

.slogan {
  color: var(--muted);
  font-size: 0.9rem;
  margin-top: 0.4rem;
}

/* 后端状态条 */
.status-line {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.6rem;
  font-size: 0.8rem;
  color: var(--muted);
  cursor: pointer;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  background: var(--card);
  border: 1px solid var(--border);
}

.status-line .dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: var(--muted);
}

.status-line.ok .dot {
  background: var(--ok);
}

.status-line.bad .dot {
  background: var(--danger);
}

/* 入口卡片：3 列网格（P4：主入口收敛为 6 个，3×2 更整齐） */
.entry-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.8rem;
}

@media (max-width: 720px) {
  .entry-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.entry-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.3rem;
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  cursor: pointer;
  color: var(--text);
  text-align: left;
  box-shadow: var(--shadow);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.entry-card:hover {
  border-color: var(--primary);
  box-shadow: var(--shadow-lg);
}

/* 图标容器：浅主色底 + 主色描边，替代原来的彩色 emoji
   （emoji 在 Windows 上彩色/单色混杂，和侧栏 SVG 风格不一致） */
.entry-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background-color: var(--primary-soft);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 34px;
}
.entry-icon :deep(.app-icon) {
  width: 19px;
  height: 19px;
}

.entry-title {
  font-size: 1.05rem;
  font-weight: 600;
}

.entry-desc {
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.5;
}

/* 次级入口 */
.minor-row {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.8rem;
  flex-wrap: wrap;
}

.minor-chip {
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--muted);
  border-radius: 999px;
  padding: 0.25rem 0.8rem;
  font-size: 0.82rem;
  cursor: pointer;
}

.minor-chip:hover {
  color: var(--primary);
  border-color: var(--primary);
}

/* 收藏/列表区块 */
.fav-section {
  margin-top: 1.4rem;
}

.fav-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.6rem;
  color: var(--text);
}

.fav-empty {
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1.7;
  margin: 0;
}

.fav-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  width: 100%;
  text-align: left;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.6rem 0.85rem;
  margin-bottom: 0.45rem;
  cursor: pointer;
  color: var(--text);
}

.fav-card:hover {
  border-color: var(--primary);
}

.fav-name {
  font-size: 0.92rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fav-cat {
  color: var(--muted);
  font-size: 0.75rem;
  flex: 0 0 auto;
}

.footnote {
  text-align: center;
  color: var(--text-light);
  font-size: 0.75rem;
  margin: 1.6rem 0 0.8rem;
}
</style>
