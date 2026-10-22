import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
// @ts-expect-error type error without @types/node package
import process from "node:process";
const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(() => ({
  plugins: [vue()],

  // 资源引用用相对路径（./assets/... 而非 /assets/...）。
  //
  // 为什么：同一份 dist 要能在两种位置工作 ——
  //   ① Tauri 壳：frontendDist 加载，根路径；
  //   ② 后端托管（不用壳的 Web 模式）：挂在 /toolbox/ 下。
  // 绝对路径 /assets/ 在第 ② 种情况下会打到后端根路径，
  // 拿到的是合迹前端的 index.html，浏览器报「MIME 类型 text/html」。
  // 相对路径在两种情况下都对（hash 路由不改变 URL 的路径部分）。
  base: "./",

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },
}));
