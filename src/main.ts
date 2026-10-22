// ============================================================
// 前端入口文件：应用启动时第一个执行的代码
// 类比：大楼的"通电总闸"——把各个系统（界面、路由、状态管理）
//       依次接上电源，大楼（应用）才能运转。
// ============================================================
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";

const app = createApp(App);

// 接入状态管理（Pinia）：全局共享的数据仓库（如"当前实验记录"）
app.use(createPinia());

// 接入路由（Router）：页面跳转系统
app.use(router);

/**
 * 启动路由：URL 带 ?route=xxx 时直接进入该页面。
 *
 * 用途：
 *   - Tauri 主壳的 devUrl 没法可靠带 hash（WebView2 会规范化掉 fragment），
 *     用 query 更稳；
 *   - 以后做「桌面快捷方式直达某个页面」也靠它。
 *
 * 例：http://localhost:1420/?route=lab  → 直接进「实验记录」
 */
const wanted = new URLSearchParams(window.location.search).get("route");
if (wanted) {
  // 延迟到路由就绪后再跳，避免和初始导航打架
  router.isReady().then(() => {
    const target = wanted.startsWith("/") ? wanted : `/${wanted}`;
    // 只允许应用内已注册的路径，防止拼错跳到空白页
    if (router.resolve(target).matched.length > 0) {
      router.replace(target);
    }
  });
}

// 挂载到 index.html 里的 #app 节点，界面开始渲染
app.mount("#app");

/**
 * 启动自检：把「当前 URL」与「IPC 是否可用」上报给主壳。
 *
 * 排查过一个问题：Tauri dev 下主 webview 停在 about:blank，
 * 但 Rust 侧读 webview.url() 拿不到真实地址。改成由前端主动上报，
 * 一条命令就能看清「页面到底加载到了哪个 URL、invoke 能不能用」。
 *
 * 只在 Tauri 环境下上报 —— 浏览器里没有 IPC，报了只会刷一条无意义的错误。
 */
if ("__TAURI_INTERNALS__" in window) {
  setTimeout(async () => {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("report_startup_info", {
        url: window.location.href,
        hash: window.location.hash,
        has_tauri: true,
      });
    } catch (e) {
      console.error("[ChemLab] 启动自检上报失败:", e);
    }
  }, 1500);
}
