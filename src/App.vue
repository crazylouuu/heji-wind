<script setup lang="ts">
// ============================================================
// 根组件（App.vue）：整个应用的"骨架"
// Day3 改造：底部 5 个 Tab（首页 / SOP / 计算器 / 记录 / 我的）
// Day7 改造：
//   - 设置落地：启动时应用字体缩放、手套模式
// 类比：App.vue 是商场的楼层结构——左侧是电梯按钮（侧栏导航），
//       右侧是各楼层的店铺（<router-view>），按哪个去哪层。
// ============================================================
import { onMounted } from "vue";
import AppIcon from "./components/AppIcon.vue";
import { applySettings } from "./utils/settings";

onMounted(() => {
  // 启动时把设置（字体缩放/手套模式）应用到界面
  applySettings();
});
</script>

<template>
  <div class="app-shell">
    <!--
      左侧主导航（原为顶部横条，2026-10-27 改为竖栏）
      原来 6 个 Tab（首页/SOP/投料表/计算器/记录/我的）平铺，
      加上「实验记录」后条目变多、语义层级也乱了。
      现在按「工作台 / 工具 / 实验 / 设置」四类重新分组：
        工作台：聚合页，所有功能的入口
        工具：  SOP 库、投料·计算、溶剂、纯化、安全、计时器
        实验：  实验记录（合迹 ChemELN，P3 已把后端并入主壳）
        设置：  备份、字体、手套模式、关于
      原来的 12 个页面一个没少，只是从「Tab」降为「一级入口下的子页面」，
      路由地址保持不变（老书签/快捷方式仍然有效）。
    -->
    <aside class="side-nav">
      <router-link to="/" class="brand">🧪 合记 ChemLab</router-link>
      <nav class="nav-groups">
        <div class="nav-group">
          <span class="nav-group-title">工作台</span>
          <router-link to="/" class="nav-item" exact-active-class="nav-on"><AppIcon name="grid" />总览</router-link>
        </div>
        <div class="nav-group">
          <span class="nav-group-title">工具</span>
          <router-link to="/sops" class="nav-item" active-class="nav-on"><AppIcon name="book" />SOP 库</router-link>
          <router-link to="/feed-table" class="nav-item" active-class="nav-on"><AppIcon name="scale" />投料·计算</router-link>
          <router-link to="/solvents" class="nav-item" active-class="nav-on"><AppIcon name="flask" />溶剂</router-link>
          <router-link to="/purify" class="nav-item" active-class="nav-on"><AppIcon name="funnel" />纯化</router-link>
          <router-link to="/safety" class="nav-item" active-class="nav-on"><AppIcon name="shield" />安全</router-link>
          <router-link to="/records" class="nav-item" active-class="nav-on"><AppIcon name="clock" />计时器·清单</router-link>
        </div>
        <div class="nav-group">
          <span class="nav-group-title">实验</span>
          <router-link to="/lab" class="nav-item" active-class="nav-on"><AppIcon name="notebook" />实验记录</router-link>
        </div>
        <div class="nav-group">
          <span class="nav-group-title">设置</span>
          <router-link to="/mine" class="nav-item" active-class="nav-on"><AppIcon name="sliders" />偏好设置</router-link>
        </div>
      </nav>
    </aside>

    <!-- 中间内容区：当前路由对应的页面渲染在这里 -->
    <main class="page">
      <router-view />
    </main>
  </div>
</template>

<style>
/* ============ 全局色板（CSS 变量）============
   只有一套浅色主题 —— 深色模式已于 2026-10-27 移除
   （电脑端实验室工具，环境光照稳定，多一套主题只增加维护成本）。

   【P4 视觉统一】色板对齐合迹 ChemELN（Ant Design 风格），
   两边现在是同一套设计语言，不再是「靛蓝工具箱 + 蓝色 ChemELN」拼贴。
   改主色只需改这里，全站 12 个页面跟着变（页面里已无硬编码品牌色）。 */
:root {
  --primary: #1677ff;       /* 主色（Ant Design 蓝） */
  --primary-dark: #0958d9;  /* 主色深（hover/按下） */
  --primary-soft: #e6f4ff;  /* 主色浅底（徽章/选中） */
  /* 浅底上的主色文字：直接用 --primary(#1677ff) 压在 --primary-soft 上
     只有 3.66:1，不达 AA 4.5:1。这个加深版是 5.50:1。 */
  --primary-on-soft: #0958d9;
  /* 实心背景专用（按钮底）。--primary(#1677ff) 配白字只有 4.10:1，
     这个深一档的版本是 5.62:1。--primary 保留给图标描边、边框、focus 环。 */
  --primary-solid: #0f62d6;
  --bg: #f5f5f5;            /* 页面背景 */
  --card: #ffffff;          /* 卡片背景 */
  --text: #1f1f1f;          /* 正文颜色 */
  --muted: #666666;         /* 次要文字 */
  --text-light: #6b6b6b;    /* 三级文字/占位（#999 对比度仅 2.85:1，不达 AA） */
  --border: #f0f0f0;        /* 分隔线/边框 */
  --border-dark: #d9d9d9;   /* 强调边框（输入框） */
  --danger: #ff4d4f;        /* 风险/警示色 */
  --danger-soft: #fff1f0;   /* 风险浅底 */
  --ok: #52c41a;            /* 完成/成功色 */
  --ok-soft: #f6ffed;       /* 成功浅底 */
  --warning: #faad14;       /* 警告色 */
  --warning-soft: #fffbe6;  /* 警告浅底 */
  --radius: 8px;            /* 统一圆角（对齐合迹） */
  --radius-sm: 6px;
  --shadow: 0 1px 2px rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02);
  --shadow-lg: 0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12);

  font-family: Inter, Avenir, Helvetica, Arial, "Microsoft YaHei", sans-serif;
  font-size: 16px;
  line-height: 24px;
  color: var(--text);
  background-color: var(--bg);
  -webkit-font-smoothing: antialiased;
}



* { box-sizing: border-box; }

body {
  margin: 0;
}

/* 大按钮 / 大点击区域（基础 44px 触控友好） */
button {
  min-height: 44px;
  font-size: 16px;
}

/* 手套模式：按钮更大（html 上有 glove class 时生效） */
html.glove button,
html.glove .nav-item,
html.glove .seg-btn,
html.glove .sub-tab {
  min-height: 56px;
  font-size: 17px;
}

/* 应用外壳：左侧竖栏 + 右侧内容
   （2026-10-27 从「顶部横导航」改成「左侧竖栏」，与合迹 ChemELN 的
    信息架构对齐 —— 原来实验记录页是 iframe 嵌合迹整页，会出现
    「顶部横条 + 左侧竖栏」双层导航，视觉上像两个产品拼在一起。） */
.app-shell {
  display: flex;
  flex-direction: row;
  height: 100vh;
}

/* 左侧导航栏：品牌 + 分组导航，自己滚动 */
.side-nav {
  flex: 0 0 220px;
  width: 220px;
  display: flex;
  flex-direction: column;
  background-color: var(--card);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  overflow-x: hidden;
}

.brand {
  display: block;
  padding: 1.05rem 1.1rem 0.95rem;
  font-weight: 700;
  font-size: 1.05rem;
  white-space: nowrap;
  color: var(--text);
  text-decoration: none;
  border-bottom: 1px solid var(--border);
}
.brand:hover { color: var(--primary); }

.nav-groups {
  padding: 0.4rem 0.55rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.nav-group { display: flex; flex-direction: column; gap: 1px; }

/* 分组小标题：弱化的层级提示，不抢导航项的视觉 */
.nav-group-title {
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  color: var(--text-light);
  padding: 0.35rem 0.6rem 0.2rem;
  user-select: none;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 40px;
  padding: 0 0.6rem;
  border-radius: var(--radius-sm);
  color: var(--muted);
  text-decoration: none;
  font-size: 0.95rem;
  line-height: 1.3;
  transition: background-color 0.12s, color 0.12s;
}

.nav-item:hover { background-color: var(--bg); color: var(--text); }

/* 当前页：主色浅底 + 主色文字（与合迹侧栏的选中态一致） */
.nav-item.nav-on {
  background-color: var(--primary-soft);
  /* 用 --primary-on-soft 而非 --primary：浅蓝底上的蓝字需要更深才够对比度 */
  color: var(--primary-on-soft);
  font-weight: 600;
}

/* 中间内容区：占满剩余空间，自己的滚动条
   min-width: 0 必须加 —— flex 子项默认 min-width:auto，
   宽表格会把侧栏挤变形 */
.page {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 1.1rem 1.5rem;
}

/* 窄窗口（<900px）时侧栏收窄，优先保证内容区可用 */
@media (max-width: 900px) {
  .side-nav { flex-basis: 168px; width: 168px; }
  .nav-item { font-size: 0.9rem; }
  .page { padding: 0.9rem; }
}
</style>
