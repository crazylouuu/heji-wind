<script setup lang="ts">
// ============================================================
// SopListView.vue —— SOP 列表页（底部 Tab：SOP）
// Day4 升级：顶部加"搜索框 + 标签筛选"。
//   - 搜索：标题/标签/正文（支持拼音首字母，如 wjh → 烷基化）
//   - 标签：多选 chips，选中多个 = 需同时包含
// 筛选组合：搜索结果 ∩ 标签筛选 共同生效
// ============================================================
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useSopsStore } from "../stores/sops";
import { matchesSop } from "../utils/searchSops";

const router = useRouter();
const store = useSopsStore();

// 页面一进入就触发加载（仓库已加载过会自动跳过）
onMounted(() => {
  store.fetchAll();
});

// ---- 搜索与筛选状态 ----
const query = ref("");           // 搜索框文字
const selectedTags = ref<string[]>([]); // 已选中的标签（多选）

// 全部标签（去重 + 排序，用于筛选 chips）
const allTags = computed(() =>
  [...new Set(store.sops.flatMap((s) => s.meta.tags))].sort(),
);

// 最终过滤结果：先过标签（AND：必须包含所有选中标签），再过搜索词
const filtered = computed(() =>
  store.sops.filter((sop) => {
    const tagOk =
      selectedTags.value.length === 0 ||
      selectedTags.value.every((t) => sop.meta.tags.includes(t));
    return tagOk && matchesSop(sop, query.value);
  }),
);

// 分组展示用的分类名（基于过滤结果）
const categories = computed(() =>
  [...new Set(filtered.value.map((s) => s.meta.category))],
);

// 点击标签 chip：切换选中状态
function toggleTag(tag: string) {
  const i = selectedTags.value.indexOf(tag);
  if (i >= 0) selectedTags.value.splice(i, 1);
  else selectedTags.value.push(tag);
}

// 点击卡片：跳到详情页
function openSop(id: string) {
  router.push(`/sops/${id}`);
}

// 把底层异常翻译成人话
// 典型场景：用浏览器（非 Tauri）打开时读不到资源目录，会抛 TypeError；
// 直接把 "Cannot read properties of undefined" 甩给用户没有意义。
function friendlyError(raw: string): string {
  const s = raw || "";
  if (/__TAURI|readTextFile|readDir|not a function/i.test(s)) {
    return "当前环境无法读取本地资源目录。SOP 需在桌面应用内打开（浏览器预览只支持后端与化学数据部分）。";
  }
  if (/ENOENT|not found|no such file/i.test(s)) {
    return "未找到 SOP 资源目录，请确认 assets/sops 已随应用安装。";
  }
  return s.length > 160 ? s.slice(0, 160) + "…" : s;
}

// 风险等级 → 徽章样式名
function riskClass(risk: string): string {
  const map: Record<string, string> = {
    low: "badge-ok",
    medium: "badge-warn",
    high: "badge-danger",
    critical: "badge-danger",
  };
  return map[risk] ?? "badge-muted";
}
</script>

<template>
  <div class="sop-list">
    <h1 class="title">SOP 库</h1>

    <!-- 搜索框：支持中文、英文、拼音、拼音首字母 -->
    <input
      v-model="query"
      class="search-box"
      type="search"
      placeholder="搜索标题 / 标签 / 试剂 / 现象（支持拼音，如 wjh）"
    />

    <!-- 标签筛选 chips（多选） -->
    <div class="tag-filter">
      <button
        v-for="tag in allTags"
        :key="tag"
        class="chip"
        :class="{ active: selectedTags.includes(tag) }"
        @click="toggleTag(tag)"
      >
        {{ tag }}
      </button>
    </div>

    <!-- 结果统计 -->
    <p class="hint count">{{ filtered.length }} 个结果</p>

    <!-- 加载中 -->
    <p v-if="store.loading" class="hint">加载中…</p>

    <!-- 加载失败 -->
    <p v-else-if="store.error" class="hint error">
      SOP 资源加载失败：{{ friendlyError(store.error) }}
    </p>

    <!-- 空列表 -->
    <p v-else-if="filtered.length === 0" class="hint">没有匹配的 SOP，换个关键词试试</p>

    <!-- 按分类分组展示过滤结果 -->
    <section v-for="cat in categories" :key="cat" class="group">
      <h2 class="group-title">{{ cat }}</h2>
      <div class="cards">
        <button
          v-for="sop in filtered.filter((s) => s.meta.category === cat)"
          :key="sop.meta.id"
          class="sop-card"
          @click="openSop(sop.meta.id)"
        >
          <div class="card-head">
            <span class="sop-title">{{ sop.meta.title }}</span>
            <span class="badge" :class="riskClass(sop.meta.risk)">{{ sop.meta.risk }}</span>
          </div>
          <div class="card-tags">
            <span v-for="t in sop.meta.tags" :key="t" class="tag">{{ t }}</span>
          </div>
          <div class="card-meta">
            <span v-if="sop.meta.scale && sop.meta.scale !== '待填写'">规模：{{ sop.meta.scale }}</span>
            <span v-if="sop.meta.temperature && sop.meta.temperature !== '待填写'">温度：{{ sop.meta.temperature }}</span>
            <span v-if="sop.meta.time && sop.meta.time !== '待填写'">时长：{{ sop.meta.time }}</span>
          </div>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.title {
  margin: 0 0 0.8rem;
  font-size: 1.3rem;
}

/* 搜索框：大输入框（手套友好） */
.search-box {
  width: 100%;
  min-height: 44px;
  padding: 0.5rem 0.9rem;
  font-size: 1rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background-color: var(--card);
  color: var(--text);
}

.search-box:focus {
  outline: none;
  border-color: var(--primary);
}

/* 标签筛选 chips：横向滚动 */
.tag-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.6rem;
}

.chip {
  min-height: 36px;
  padding: 0.2rem 0.8rem;
  font-size: 0.85rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background-color: var(--card);
  color: var(--muted);
  cursor: pointer;
}

.chip.active {
  background-color: var(--primary-solid);
  border-color: var(--primary);
  color: #ffffff;
}

.count {
  text-align: left;
  padding: 0.4rem 0 0;
  font-size: 0.8rem;
}

.hint {
  color: var(--muted);
  text-align: center;
  padding: 2rem 0;
}

.hint.error {
  color: var(--danger);
}

.group-title {
  font-size: 1rem;
  color: var(--muted);
  margin: 1.2rem 0 0.5rem;
  border-left: 3px solid var(--primary);
  padding-left: 0.5rem;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.sop-card {
  width: 100%;
  text-align: left;
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.9rem 1rem;
  cursor: pointer;
  color: var(--text);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.sop-card:hover {
  border-color: var(--primary);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.sop-title {
  font-size: 1.05rem;
  font-weight: 600;
}

.badge {
  font-size: 0.75rem;
  padding: 0.1rem 0.6rem;
  border-radius: 999px;
  white-space: nowrap;
}
.badge-danger { background-color: var(--danger-soft); color: var(--danger); }
.badge-warn   { background-color: #fef3c7; color: #b45309; }
.badge-ok     { background-color: #dcfce7; color: var(--ok); }
.badge-muted  { background-color: var(--primary-soft); color: var(--primary); }

.card-tags {
  margin-top: 0.4rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.tag {
  font-size: 0.72rem;
  padding: 0.05rem 0.5rem;
  border-radius: 999px;
  background-color: var(--primary-soft);
  color: var(--primary);
}

.card-meta {
  margin-top: 0.4rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  font-size: 0.8rem;
  color: var(--muted);
}
</style>
