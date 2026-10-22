---
name: 合记 ChemLab
description: 有机合成实验室的日常工具台 —— 查 SOP → 算投料 → 看安全 → 执行 → 计时 → 记录 → 复盘
colors:
  primary: "#1677ff"
  primary-dark: "#0958d9"
  primary-soft: "#e6f4ff"
  primary-on-soft: "#0958d9"
  primary-solid: "#0f62d6"
  neutral-bg: "#f5f5f5"
  surface: "#ffffff"
  text: "#1f1f1f"
  text-muted: "#666666"
  text-light: "#999999"
  border: "#f0f0f0"
  border-strong: "#d9d9d9"
  danger: "#ff4d4f"
  danger-soft: "#fff1f0"
  success: "#52c41a"
  success-soft: "#f6ffed"
  warning: "#faad14"
  warning-soft: "#fffbe6"
typography:
  body:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  page-title:
    fontFamily: "Inter, 'Microsoft YaHei', sans-serif"
    fontSize: "1.6rem"
    fontWeight: 700
    lineHeight: 1.25
  section-title:
    fontFamily: "Inter, 'Microsoft YaHei', sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
  card-title:
    fontFamily: "Inter, 'Microsoft YaHei', sans-serif"
    fontSize: "1.05rem"
    fontWeight: 600
    lineHeight: 1.35
  nav-item:
    fontFamily: "Inter, 'Microsoft YaHei', sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.3
  caption:
    fontFamily: "Inter, 'Microsoft YaHei', sans-serif"
    fontSize: "0.85rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: "6px"
  md: "8px"
  lg: "9px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "16px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.sm}"
    height: "40px"
    padding: "0 12px"
    typography: "{typography.nav-item}"
  nav-item-active:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    height: "44px"
    padding: "0 15px"
  badge-warning:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
  sidebar:
    backgroundColor: "{colors.surface}"
    width: "220px"
---

## Overview

合记 ChemLab 是一个**双前端**应用：Vue 工具箱（12 个视图）+ 合迹 ChemELN（9 个视图，由 iframe 嵌入）。
两块代码来自不同时期，但视觉语言是同一套（Ant Design 风格的蓝白灰）。
本文件是**唯一的视觉规范来源** —— 改动任何界面样式前先看这里，改完把新规则补回来。

**只有一套浅色主题**，没有深色模式 —— 电脑端实验室工具，环境光照稳定，
多维护一套主题不划算（2026-10-27 移除了原有的深色模式与 data-theme 机制）。

界面定位是 **Operate 模式**：用户在实验室里完成具体任务（查规程、算投料、看应急）。
所以规范的第一目标是**可扫描、可信任、不干扰**，不是表达个性。
品牌感体现在精确的对齐、克制的配色和一致的圆角上，不靠装饰。

### 两套前端的变量名映射（值完全相同）

改样式时常踩的坑：同一份设计在两个代码库里叫不同名字。

| 语义 | 工具箱（Vue，`src/App.vue`） | 合迹（原生 CSS，`frontend-chemeln/css/style.css`） |
| --- | --- | --- |
| 主色 | `--primary` | `--primary` |
| 主色深 | `--primary-dark` | `--primary-dark` |
| 主色浅底 | `--primary-soft` | `--primary-light` |
| 页面背景 | `--bg` | `--bg` |
| 卡片背景 | `--card` | `--bg-card` |
| 正文 | `--text` | `--text` |
| 次要文字 | `--muted` | `--text-muted` |
| 三级文字 | `--text-light` | `--text-light` |
| 边框 | `--border` | `--border` |
| 强调边框 | `--border-dark` | `--border-dark` |
| 危险 / 成功 / 警告 | `--danger` / `--ok` / `--warning` | `--danger` / `--success` / `--warning` |
| 对应浅底 | `--danger-soft` / `--ok-soft` / `--warning-soft` | `--danger-light` / `--success-light` / `--warning-light` |
| 圆角 | `--radius` (8px) / `--radius-sm` (6px) | `--radius` / `--radius-sm` |

## Colors

只有一个品牌色：**#1677ff**（Ant Design 蓝）。它表达"可点、选中、进行中"，不用于装饰。

- **主色只出现在四处**：当前导航项、主按钮、链接、选中态边框。页面里其余部分全用中性色。
- **浅底配主色文字**是一组固定搭配（`--primary-soft` + `--primary`）。导航选中、Tab 选中、次级按钮都用它。
- **语义色成对使用**：`--danger` 配 `--danger-soft`、`--ok` 配 `--ok-soft`、`--warning` 配 `--warning-soft`。不单独使用浅底，也不单独用深色铺大面积。
- **不要引入第二个品牌色**。合迹里残留的 `--bg-sidebar: #4D6BFE` 和 `--accent: #722ed1` 是历史遗留，只用于已隐藏的旧顶部栏，新代码不要引用。

### 三个主色的分工（不要混用）

`#1677ff` 本身达不到 WCAG AA 的文字对比度要求（白底 4.10:1、白字 4.10:1），所以拆成三个用途明确的 token：

| Token | 值 | 用在哪 | 对比度 |
| --- | --- | --- | --- |
| `--primary` | `#1677ff` | 图标描边、边框、focus 环（**非文字**，3:1 标准） | — |
| `--primary-on-soft` | `#0958d9` | 浅主色底上的文字（导航选中、Tab 选中） | 5.50:1 |
| `--primary-solid` | `#0f62d6` | 实心背景 + 白字（主按钮） | 5.62:1 |

**规则**：只要是"文字压在某色上"，就必须查对比度 ≥ 4.5:1。`--primary` 不能直接当文字色或实心按钮底色用。

## Typography

**基准 16px**，这是硬约束 —— 两套前端都统一到它（合迹原来 14px，2026-10-27 已整体上调）。

- 正文 16px / 行高 1.5。表格可降到 14px（信息密度需要），但不再往下。
- 页面标题 `1.6rem` + 700；区块标题 `1rem` + 600；卡片标题 `1.05rem` + 600。
- 导航项 `0.95rem`，选中时只加 `font-weight: 600`，**不加字号**（否则切换时文字会跳）。
- 字体栈首位是 Inter，中文回退 Microsoft YaHei。不要引入网络字体 —— 这是离线桌面工具。
- 纯数字表格（投料量、分子量）用 `font-variant-numeric: tabular-nums` 保持列对齐。
- **三级文字 `--text-light` 是 `#6b6b6b`**，不是原来的 `#999999`。
  `#999` 在白底上只有 2.85:1，读起来费劲，审计时被判为不合格。占位符也用它。

## Layout

- **左侧竖栏固定 220px**（<900px 时收到 168px），右侧内容区自适应。不用顶部横导航。
- 内容区 `padding: 1.1rem 1.5rem`，最大宽度不限（实验室屏幕宽，表格需要横向空间）。
- 卡片间距 16px，卡片内边距 16px。
- 侧栏导航按语义分组（工作台 / 工具 / 实验 / 设置），分组标题 `0.72rem` + 三级文字色，只做层级提示不抢视觉。
- **flex 子项必须写 `min-width: 0`** —— 宽表格会把侧栏挤变形，这是本项目踩过的坑。

## Elevation & Depth

只有两级阴影，都用得很轻：

- `--shadow`：卡片的默认状态，几乎看不见（`0 1px 2px rgba(0,0,0,0.03)`），作用是把白卡从 #f5f5f5 背景上"抬"起来一点。
- `--shadow-lg`：浮层、弹窗、下拉菜单。

**不用阴影表达层级**。层级靠背景色差（#fff 卡片 vs #f5f5f5 页面）和边框（#f0f0f0）区分。
不要加大阴影、不要发光效果。

## Shapes

- 圆角只有三档：`6px`（小元素、徽章、按钮）、`8px`（卡片、输入框）、`9px`（图标底块）。
- 图标统一用内联 SVG 线性风格：24×24 viewBox、`stroke-width: 1.75`、圆角端点、`stroke="currentColor"`。
  **不用 emoji** —— Windows 上 emoji 会混用彩色/单色两套字体，同一列里粗细不一。
- 图标默认 18px；卡片入口里的图标放在 34px 浅主色方块里，图标本身 19px。

## Components

- **导航项**：高 40px、圆角 6px、左侧 18px 图标 + 文字间距 8px。未选中 `--text-muted`，hover 时背景 `--bg`，选中 `--primary-soft` 底 + `--primary` 字 + 600 字重。
- **卡片**：白底、8px 圆角、1px `--border` 边框、16px 内边距、`--shadow`。卡片本身不可点击（内部元素可点），除非整卡是一个入口。
- **主按钮**：主色底 + 白字、6px 圆角、高 44px。次要按钮用白底 + `--border-dark` 边框。同一屏最多一个主按钮。
- **徽章**：语义浅底 + 语义深色字、6px 圆角、`2px 8px` 内边距、`0.85rem`。用于风险等级、状态、标签。
- **表格**：表头 `--bg` 底、`--text-muted` 字；行分隔用 1px `--border`；不用斑马纹（实验室数据靠列对齐识别，不靠底色）。

## Do's and Don'ts

**Do**
- 改样式前先查上面两张表，用变量而不是写死色值。
- 新增图标往 `src/components/AppIcon.vue` 里加，保持 24×24 / stroke 1.75 / currentColor。
- 两套前端要一起改的地方，先确认变量名映射（`--card` vs `--bg-card`）。
- 数值类内容用 `tabular-nums`，风险等级用语义色 + 文字（不只靠颜色）。

**Don't**
- 不要引入第二个品牌色或渐变。
- 不要把字号调回 14px 以下（基准 16px 是定过的）。
- 不要用 emoji 当界面图标（状态符号 ★ ✓ ✕ 除外，它们嵌在文字里）。
- 不要用大阴影、发光、玻璃拟态表达层级。
- 不要在 iframe 里再放一套导航（合迹的 `?embed=1` 就是干这个的）。
- 不要为了"好看"改主按钮的文字 —— 按钮文案属于产品规范，不属于视觉规范。
