<script setup lang="ts">
// ============================================================
// LabView.vue —— 实验记录（合记 ChemELN）
//
// 两种嵌入方式，按优先级自动选择：
//
//   ① child —— Tauri 原生子 webview（P5）
//      同一桌面窗口内多一个原生 webview 控件，无 iframe 边框/沙箱限制。
//      主壳 → 子页：Rust eval 注入 window.__chemlabNav(view)
//      子页 → 主壳：子页 POST /api/lab/events 报 ready，主壳轮询后端得知
//      （on_page_load 对子 webview 不可靠，不能用来判断就绪）
//
//   ② iframe —— 纯 Web 标准方案（P4 留下的降级路径）
//      主壳 → 子页：postMessage（chemlab:invoke / navigate）
//      子页 → 后端：同源 fetch + 令牌头
//
// 选哪一种：能调 Tauri 命令（说明在主壳里）且子 webview 创建成功 → child；
// 否则退回 iframe。子 webview 5 秒没就绪也退回 iframe，保证功能不中断。
// ============================================================
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { getBackendStatus, type BackendStatus } from "../utils/backend";

/** 顶部分段器：与合迹侧栏的视图名一一对应 */
const VIEWS = [
  { key: "dashboard", label: "仪表盘" },
  { key: "experiments", label: "实验记录" },
  { key: "kanban", label: "看板" },
  { key: "compounds", label: "化合物库" },
  { key: "templates", label: "模板" },
  { key: "tags", label: "标签" },
  { key: "data", label: "导入导出" },
];

type Mode = "child" | "iframe";

const be = ref<BackendStatus | null>(null);
const mode = ref<Mode>("iframe");
const activeView = ref("dashboard");
const frameReady = ref(false);
const loading = ref(true);
const labError = ref("");

const frameEl = ref<HTMLIFrameElement | null>(null);
const slotEl = ref<HTMLElement | null>(null);

const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

/** 后端地址（主壳托管，端口默认 8765） */
const backendUrl = computed(() => {
  const base = be.value?.base_url;
  if (!base) return "";
  return base.replace(/\/$/, "");
});

/** iframe 模式下的加载地址
 *
 * 带 `?embed=1` 让合迹隐藏它自己的顶部栏和左侧栏 ——
 * 工具箱在 iframe 外面已经有一份左侧导航了，两份叠在一起
 * 就是「两条竖栏并排」，看起来像两个应用拼在一起。
 *
 * 只对 iframe 加：child（Tauri 原生子 webview）不受外层侧栏影响，
 * 那边需要合迹保留自己的导航供切换视图。
 */
const frameSrc = computed(() =>
  backendUrl.value ? `${backendUrl.value}/?embed=1` : "",
);

// ---------------------------------------------------------------- child 模式

/** 轮询句柄 */
let pollTimer: number | null = null;

/** 把主 webview 里本组件所占的矩形告诉主壳，让子 webview 精确贴合 */
async function placeChild(visible: boolean) {
  const el = slotEl.value;
  if (!el) return;
  const r = el.getBoundingClientRect();
  try {
    await invoke("lab_place", {
      x: r.left,
      y: r.top,
      w: r.width,
      h: r.height,
      visible,
    });
  } catch {
    /* 命令不可用时忽略（浏览器预览） */
  }
}

/** 轮询子页是否就绪 */
async function pollChild() {
  const st = be.value;
  if (!st) return;
  try {
    const s = await invoke<{ ready: boolean; open: boolean; error: string | null }>(
      "lab_poll",
      { token: st.token, port: st.port },
    );
    if (s.ready) {
      frameReady.value = true;
      loading.value = false;
      stopPoll();
      return;
    }
    if (s.error) {
      labError.value = s.error;
    }
  } catch {
    /* 命令不可用 → 由降级逻辑接管 */
  }
}

function startPoll() {
  stopPoll();
  pollTimer = window.setInterval(pollChild, 500);
}

function stopPoll() {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

/** 切换视图 */
async function switchView(view: string) {
  activeView.value = view;
  if (mode.value === "child") {
    try {
      await invoke("lab_nav", { view });
    } catch (e) {
      labError.value = String(e);
    }
    return;
  }
  sendToFrame("navigate", { view });
}

/** 打开子 webview；失败或超时则降级到 iframe */
async function openChild(): Promise<boolean> {
  const st = be.value;
  if (!st || !st.running || !backendUrl.value) return false;
  try {
    const res = await invoke<{ open: boolean; error: string | null }>("lab_open", {
      url: backendUrl.value,
    });
    if (res.error) {
      labError.value = res.error;
      return false;
    }
  } catch (e) {
    labError.value = String(e);
    return false;
  }

  mode.value = "child";
  await nextTick();
  await placeChild(true);
  startPoll();

  // 最多等 8 秒；超时就退回 iframe（保证功能不中断）
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 400));
    if (frameReady.value) return true;
  }
  labError.value = "子 webview 启动超时，已切换到 iframe 模式";
  await fallbackToIframe();
  return false;
}

/** 降级到 iframe */
async function fallbackToIframe() {
  stopPoll();
  mode.value = "iframe";
  loading.value = true;
  frameReady.value = false;
  try {
    await invoke("lab_close");
  } catch {
    /* 忽略 */
  }
}

// ---------------------------------------------------------------- iframe 模式

/** 向 iframe 子页发指令 */
function sendToFrame(method: string, params: Record<string, unknown> = {}) {
  const f = frameEl.value;
  if (!f || !f.contentWindow) return;
  f.contentWindow.postMessage(
    { type: "chemlab:invoke", id: Date.now(), method, params },
    backendUrl.value || "*",
  );
}

/** 收 iframe 子页的回复 */
function onMessage(e: MessageEvent) {
  const msg = e.data;
  if (!msg || msg.type !== "chemlab:response") return;
  if (msg.ok) {
    frameReady.value = true;
    loading.value = false;
  }
}

/** 重新加载（后端重启后用） */
function reload() {
  frameReady.value = false;
  loading.value = true;
  if (mode.value === "iframe") {
    const f = frameEl.value;
    if (f) {
      const base = f.src.split("&r=")[0];
      f.src = `${base}&r=${Date.now()}`;
    }
  } else {
    openChild();
  }
}

function onResize() {
  if (mode.value === "child") placeChild(true);
}

onMounted(async () => {
  window.addEventListener("message", onMessage);
  window.addEventListener("resize", onResize);
  be.value = await getBackendStatus(true);
  if (isTauri && be.value?.running) {
    await openChild();
  } else {
    mode.value = "iframe";
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("message", onMessage);
  window.removeEventListener("resize", onResize);
  stopPoll();
  // 离开页面时把子 webview 挪出客户区（Webview 没有 set_visible）
  if (mode.value === "child") placeChild(false);
});
</script>

<template>
  <div class="lab">
    <!-- 顶部分段器：控制嵌入页显示哪一块 -->
    <div class="lab-bar">
      <div class="seg">
        <button
          v-for="v in VIEWS"
          :key="v.key"
          class="seg-btn"
          :class="{ on: activeView === v.key }"
          @click="switchView(v.key)"
        >
          {{ v.label }}
        </button>
      </div>
      <div class="lab-tools">
        <span class="lab-mode">{{ mode === "child" ? "原生内嵌" : "兼容模式" }}</span>
        <span class="lab-state" :class="be?.running ? 'ok' : 'bad'">
          {{ be?.running ? "后端已连接" : "后端未就绪" }}
        </span>
        <button class="btn-mini" @click="reload" :disabled="!be?.running">刷新</button>
      </div>
    </div>

    <!-- 后端不可用 -->
    <div v-if="be && !be.running" class="lab-empty">
      <p class="lab-empty-title">实验记录服务未就绪</p>
      <p class="lab-empty-desc">
        {{ be.error || "后端进程没有启动成功" }}
      </p>
      <p v-if="be.log_path" class="lab-empty-log">日志：{{ be.log_path }}</p>
      <button class="btn-main" @click="reload">重新检测</button>
    </div>

    <!-- 正常：child 模式留占位（子 webview 会盖在上面），iframe 模式直接嵌 -->
    <div v-else class="lab-body">
      <!-- child 模式的占位槽：尺寸用于让子 webview 精确贴合 -->
      <div ref="slotEl" class="lab-slot">
        <div v-if="!frameReady" class="lab-loading">
          正在加载实验记录…<span v-if="labError" class="lab-loading-err">{{ labError }}</span>
        </div>
      </div>

      <iframe
        v-if="mode === 'iframe'"
        ref="frameEl"
        class="lab-frame"
        :src="frameSrc"
        title="实验记录"
        @load="loading = false; frameReady = true"
      ></iframe>
    </div>
  </div>
</template>

<style scoped>
.lab {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* 顶部分段器 */
.lab-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0 0.2rem 0.6rem;
  flex-wrap: wrap;
}

.seg {
  display: flex;
  gap: 0.2rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.2rem;
  overflow-x: auto;
}

.seg-btn {
  border: none;
  background: transparent;
  color: var(--muted);
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.9rem;
  min-height: 34px;
  white-space: nowrap;
}

.seg-btn:hover {
  color: var(--primary);
}

.seg-btn.on {
  background: var(--primary-solid);
  color: #fff;
  font-weight: 600;
}

.lab-tools {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.lab-mode {
  font-size: 0.75rem;
  color: var(--text-light);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
}

.lab-state {
  font-size: 0.8rem;
  color: var(--muted);
}

.lab-state.ok::before {
  content: "● ";
  color: var(--ok);
}

.lab-state.bad::before {
  content: "● ";
  color: var(--danger);
}

.btn-mini {
  border: 1px solid var(--border-dark);
  background: var(--card);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 0.25rem 0.7rem;
  font-size: 0.8rem;
  cursor: pointer;
  min-height: 30px;
}

.btn-mini:disabled {
  opacity: 0.5;
  cursor: default;
}

/* 内容区 */
.lab-body {
  position: relative;
  flex: 1;
  min-height: 0;
}

/* child 模式占位槽：子 webview 覆盖在这个位置 */
.lab-slot {
  position: absolute;
  inset: 0;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

/* iframe 模式 */
.lab-frame {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
}

.lab-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  color: var(--muted);
  font-size: 0.9rem;
  background: var(--card);
}

.lab-loading-err {
  font-size: 0.78rem;
  color: var(--danger);
}

/* 后端不可用 */
.lab-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 2rem;
  text-align: center;
}

.lab-empty-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
}

.lab-empty-desc {
  color: var(--muted);
  margin: 0;
  font-size: 0.9rem;
  max-width: 520px;
}

.lab-empty-log {
  color: var(--text-light);
  font-size: 0.75rem;
  margin: 0;
  word-break: break-all;
}
</style>
