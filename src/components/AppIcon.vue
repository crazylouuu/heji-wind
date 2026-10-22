<script lang="ts">
// 图标名集中在这里导出，页面可按名引用（type 在编译期擦除，不进产物）
export type IconName =
  // 导航 / 功能入口
  | "grid"
  | "book"
  | "scale"
  | "flask"
  | "funnel"
  | "shield"
  | "clock"
  | "notebook"
  | "sliders"
  // 设置页分组
  | "database"
  | "server"
  // 安全应急场景
  | "wind"
  | "droplet"
  | "flame"
  | "trash"
  // 页面标题 / 段落图标
  | "fileText"
  | "listChecks"
  | "info";
</script>

<script setup lang="ts">
// ============================================================
// AppIcon —— 全站统一图标（内联 SVG 线性图标）
//
// 为什么不直接用 emoji：Windows 上 emoji 会混用两套字体渲染 ——
// Segoe UI Emoji 出彩色、Segoe UI Symbol 出单色线稿。同一列导航里
// ⚖️ 是彩色而 📖 是灰色线稿，同一张卡片里 💨 和 🔥 的笔画粗细也不同，
// 看起来像没做完。SVG 的线宽、端点、尺寸都完全可控。
//
// 为什么用 currentColor 描边：图标颜色跟随父元素文字色 ——
// 导航项选中时文字变主色，图标自动跟着变，不用写额外的选中态规则。
//
// 图形统一为 24×24 线性风格（stroke 1.75、圆角端点），
// 显示尺寸由使用处 CSS 控制（默认 18px），不在此处写死。
//
// 注意：纯文本里的状态符号（★ 收藏、⚠️ 风险提示、✅ 完成）
// 不换成图标 —— 它们嵌在句子中间，SVG 反而会破坏文字排版。
// ============================================================

defineProps<{ name: IconName }>();

/// 每个图标只存「内容」，外层 <svg> 由模板统一提供，
/// 保证所有图标的线宽/端点风格完全一致。
const PATHS: Record<IconName, string> = {
  // ---------- 导航 ----------
  // 总览：四宫格
  grid: `<rect x="3" y="3" width="7.5" height="7.5" rx="1.5"/>
         <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5"/>
         <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5"/>
         <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5"/>`,
  // SOP 库：翻开的书
  book: `<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
         <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>`,
  // 投料·计算：天平
  scale: `<path d="M12 3.5v17"/>
          <path d="M6 6.5h12"/>
          <path d="M4 6.5 1.5 14a3.5 3.5 0 0 0 5 0L4 6.5z"/>
          <path d="M20 6.5 17.5 14a3.5 3.5 0 0 0 5 0L20 6.5z"/>`,
  // 溶剂：锥形瓶
  flask: `<path d="M9.5 3h5"/>
          <path d="M10.5 3v6.2l-4.9 8.5A1.8 1.8 0 0 0 7.2 20.5h9.6a1.8 1.8 0 0 0 1.6-2.8l-4.9-8.5V3"/>
          <path d="M7.5 15.5h9"/>`,
  // 纯化：漏斗
  funnel: `<path d="M3.5 4.5h17l-6.6 7.6v6.2l-3.8 2.2v-8.4L3.5 4.5z"/>`,
  // 安全：盾牌 + 勾
  shield: `<path d="M12 3 20 6v6.2c0 4.7-3.4 7.9-8 8.8-4.6-.9-8-4.1-8-8.8V6l8-3z"/>
           <path d="m9 12 2.2 2.2L15.5 10"/>`,
  // 计时器：钟
  clock: `<circle cx="12" cy="13.5" r="7.5"/>
          <path d="M12 9.5v4l2.6 2.2"/>
          <path d="M9.5 2.5h5"/>`,
  // 实验记录：笔记本
  notebook: `<rect x="4.5" y="3" width="15" height="18" rx="2"/>
             <path d="M8.5 3v18"/>
             <path d="M12 8h4.5"/>
             <path d="M12 12.5h4.5"/>`,
  // 偏好设置：滑杆
  sliders: `<path d="M3.5 7h17"/>
            <path d="M3.5 12h17"/>
            <path d="M3.5 17h17"/>
            <circle cx="8.5" cy="7" r="2.2"/>
            <circle cx="15.5" cy="12" r="2.2"/>
            <circle cx="10.5" cy="17" r="2.2"/>`,

  // ---------- 设置页分组 ----------
  // 数据：数据库
  database: `<ellipse cx="12" cy="5.5" rx="8" ry="3"/>
             <path d="M4 5.5v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/>
             <path d="M4 11.5v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/>`,
  // 后端服务：机架
  server: `<rect x="3" y="4" width="18" height="7" rx="1.8"/>
           <rect x="3" y="13" width="18" height="7" rx="1.8"/>
           <path d="M7 7.5h.01"/>
           <path d="M7 16.5h.01"/>`,

  // ---------- 安全应急场景 ----------
  // 气体泄漏：流动的风
  wind: `<path d="M3 8h11a3 3 0 1 0-3-3"/>
         <path d="M3 12h15a3 3 0 1 1-3 3"/>
         <path d="M3 16h8"/>`,
  // 液体溅到：水滴
  droplet: `<path d="M12 3.5c3.5 4 6 6.9 6 9.5a6 6 0 0 1-12 0c0-2.6 2.5-5.5 6-9.5z"/>`,
  // 着火：火焰
  flame: `<path d="M12 3c3 4 5.5 6.2 5.5 9.5A5.5 5.5 0 0 1 12 18a5.5 5.5 0 0 1-5.5-5.5C6.5 9.2 9 7 12 3z"/>
          <path d="M12 18a2.6 2.6 0 0 1-2.6-2.6c0-1.5 1.4-2.9 2.6-4.4 1.2 1.5 2.6 2.9 2.6 4.4A2.6 2.6 0 0 1 12 18z"/>`,
  // 废弃物：垃圾桶
  trash: `<path d="M4 7h16"/>
          <path d="M9.5 7V5.2A1.2 1.2 0 0 1 10.7 4h2.6a1.2 1.2 0 0 1 1.2 1.2V7"/>
          <path d="M6.5 7 7.6 19.6A1.6 1.6 0 0 0 9.2 21h5.6a1.6 1.6 0 0 0 1.6-1.4L17.5 7"/>
          <path d="M10.5 11v6"/>
          <path d="M13.5 11v6"/>`,

  // ---------- 页面标题 / 段落图标 ----------
  // 文档：免责声明等
  fileText: `<path d="M14 3H7.5A2.5 2.5 0 0 0 5 5.5v13A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V8l-5-5z"/>
             <path d="M14 3v5h5"/>
             <path d="M9 13h6"/>
             <path d="M9 17h4"/>`,
  // 清单：带勾的列表
  listChecks: `<path d="M4 6.5 5.4 8 8 5.2"/>
               <path d="M4 12.2 5.4 13.7 8 10.9"/>
               <path d="M4 17.9 5.4 19.4 8 16.6"/>
               <path d="M11 7h9"/>
               <path d="M11 12.5h9"/>
               <path d="M11 18h9"/>`,
  // 信息
  info: `<circle cx="12" cy="12" r="9"/>
         <path d="M12 11v5.5"/>
         <path d="M12 7.8h.01"/>`,
};
</script>

<template>
  <svg
    class="app-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.75"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="PATHS[name]"
  />
</template>

<style scoped>
.app-icon {
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  display: block;
}
</style>
