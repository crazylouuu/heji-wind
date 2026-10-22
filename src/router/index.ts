// ============================================================
// 路由表：负责"URL 路径 → 页面组件"的映射
// 类比：路由器 = 大楼前台，来访者（URL）报出房间号（路径），
//       前台就把他带到对应房间（页面组件）。
// Day3：新增 5 个 Tab 对应的页面 + SOP 详情页
// ============================================================
import { createRouter, createWebHashHistory } from "vue-router";

// 路由表：每个 Tab 一行；懒加载（进入该页才加载组件，启动更快）
const routes = [
  {
    path: "/",                                     // 首页 Tab
    name: "home",
    component: () => import("../views/HomeView.vue"),
  },
  {
    path: "/sops",                                 // SOP 列表 Tab
    name: "sop-list",
    component: () => import("../views/SopListView.vue"),
  },
  {
    path: "/sops/:id",                             // SOP 详情（:id 是动态参数）
    name: "sop-detail",
    component: () => import("../views/SopDetailView.vue"),
  },
  {
    path: "/feed-table",                           // 投料计划表 Tab（2026-09-24 从计算器剥离独立）
    name: "feed-table",
    component: () => import("../views/FeedTableView.vue"),
  },
  {
    path: "/calculator",                           // 计算器 Tab（Day5 开发）
    name: "calculator",
    component: () => import("../views/CalculatorView.vue"),
  },
  {
    path: "/records",                              // 记录 Tab（Day7 开发）
    name: "records",
    component: () => import("../views/RecordsView.vue"),
  },
  {
    path: "/mine",                                 // 我的 Tab（Day7 开发）
    name: "mine",
    component: () => import("../views/MineView.vue"),
  },
  {
    path: "/safety",                               // 安全应急页（Day7，从我的页进入）
    name: "safety",
    component: () => import("../views/SafetyView.vue"),
  },
  {
    path: "/purify",                               // 纯化操作（2026-09-24 首页快捷入口）
    name: "purify",
    component: () => import("../views/PurificationView.vue"),
  },
  {
    path: "/solvents",                             // 溶剂查询（2026-09-24 首页快捷入口）
    name: "solvents",
    component: () => import("../views/SolventView.vue"),
  },
  {
    path: "/solvents/:id",                         // 溶剂详情（0.8.0 新增：列表精简，点行进详情）
    name: "solvent-detail",
    component: () => import("../views/SolventDetailView.vue"),
  },
  {
    path: "/lab",                                 // 实验记录（P4：iframe 嵌入合迹 ChemELN）
    name: "lab",
    component: () => import("../views/LabView.vue"),
  },
];

// 创建路由实例
// hash 模式（URL 形如 xxx.html#/）：桌面应用加载本地文件，
// 无服务器做路径重写，hash 模式最稳（后续鸿蒙同样适用）
const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
