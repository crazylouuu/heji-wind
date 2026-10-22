<script setup lang="ts">
// ============================================================
// MineView.vue —— 设置中心（P4 起顶部导航叫「设置」）
// 包含：
//   1. 字体大小（整体缩放：小/中/大）
//   2. 手套模式（按钮更大）
//   5. 数据备份：一键导出 JSON 状态备份（收藏/勾选/设置等，不含实验记录）
//   6. 安全应急入口
//   7. 关于 + 免责声明
// 所有设置即时生效并保存到 localStorage
// 【2026-09-23】实验记录功能停用（数据泄露风险）：备份文件不再包含实验记录
// ============================================================
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { downloadText, stampedName } from "../utils/download";
import { APP_NAME, APP_VERSION } from "../utils/appInfo"; // 版本号自动跟随 package.json
import {
  type AppSettings,
  loadSettings,
  saveSettings,
  applySettings,
  type FontScale,
} from "../utils/settings";
import {
  getBackendStatus,
  restartBackend,
  type BackendStatus,
} from "../utils/backend";

const router = useRouter();

// 当前设置（reactive 副本，改动即保存并应用）
const s = ref<AppSettings>(loadSettings());

onMounted(applySettings); // 启动时把设置应用到界面

// ---- 后端服务状态（P3：后端由主壳统一托管）----
const be = ref<BackendStatus | null>(null);
const beBusy = ref(false);
// 操作结果提示（替代 alert：壳退出后 alert 会阻塞，提示条更轻）
const notice = ref("");

async function loadBackend() {
  be.value = await getBackendStatus(true);
}

async function doRestartBackend() {
  beBusy.value = true;
  try {
    be.value = await restartBackend();
  } finally {
    beBusy.value = false;
  }
}

onMounted(loadBackend);

// 通用：保存设置并应用
function update(partial: Partial<AppSettings>) {
  s.value = { ...s.value, ...partial };
  saveSettings(s.value);
  applySettings();
}

// 字体大小三选
function setFont(v: FontScale) {
  update({ fontScale: v });
}

// 手套模式开关
function setGlove(v: boolean) {
  update({ gloveMode: v });
}

// ---- 状态备份（JSON）----
// 【2026-09-23】实验记录功能已停用（数据泄露风险），备份文件同样不再包含
// 实验记录数据，只备份本地状态（收藏/勾选/设置/计时器等），避免敏感实验
// 内容散落到备份文件中。
async function backupAll() {
  // 收集 localStorage 里本应用的所有数据（统一 heji_ 前缀）
  const local: Record<string, unknown> = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith("heji_")) {
      try {
        local[k] = JSON.parse(localStorage.getItem(k) || "");
      } catch {
        local[k] = localStorage.getItem(k);
      }
    }
  }

  const payload = {
    app: APP_NAME,
    version: APP_VERSION, // 自动跟随 package.json
    exportedAt: new Date().toISOString(),
    localState: local, // 收藏/勾选/设置/计时器等（不含实验记录）
  };

  // 走浏览器下载：壳在启动器模式下会退出，dialog/fs 插件不可用
  const name = stampedName("合记ChemLab_状态备份", "json");
  downloadText(name, JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
  notice.value = `状态备份已下载：${name}`;
}

// ---- 导入状态备份 ----
// 只接受本应用导出的格式，且只写入 heji_ 前缀的键 ——
// 避免把别人文件里的无关数据灌进 localStorage。
const fileEl = ref<HTMLInputElement | null>(null);
const pendingImport = ref<{ fileName: string; payload: BackupPayload } | null>(null);

interface BackupPayload {
  app?: string;
  version?: string;
  exportedAt?: string;
  localState?: Record<string, unknown>;
}

/// 预览里显示的数量必须和真正会写入的数量一致 ——
/// 只数 heji_ 前缀，否则会出现"说 3 项、实际导入 2 项"的错觉。
function importableCount(localState: Record<string, unknown> | undefined): number {
  if (!localState) return 0;
  return Object.keys(localState).filter((k) => k.startsWith("heji_")).length;
}

function pickImport() {
  fileEl.value?.click();
}

async function onFilePicked(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    const data = JSON.parse(await file.text()) as BackupPayload;
    if (!data || typeof data !== "object" || !data.localState || typeof data.localState !== "object") {
      throw new Error("这不是本应用的状态备份文件（缺少 localState）");
    }
    pendingImport.value = { fileName: file.name, payload: data };
    notice.value = "";
  } catch (err) {
    pendingImport.value = null;
    notice.value = "读取失败：" + (err instanceof Error ? err.message : String(err));
  } finally {
    // 清空 value，否则再次选同一个文件不会触发 change
    input.value = "";
  }
}

function confirmImport() {
  const p = pendingImport.value;
  if (!p) return;
  let n = 0;
  for (const [k, v] of Object.entries(p.payload.localState ?? {})) {
    if (!k.startsWith("heji_")) continue;
    localStorage.setItem(k, typeof v === "string" ? v : JSON.stringify(v));
    n++;
  }
  // 设置可能被覆盖，重新读一遍并立即生效
  s.value = loadSettings();
  applySettings();
  pendingImport.value = null;
  notice.value = `已导入 ${n} 项状态。若某些页面没变，刷新一下（Ctrl+F5）。`;
}
</script>

<template>
  <div class="mine">
    <h1 class="title">设置</h1>

    <!-- 外观设置 -->
    <section class="card">
      <h2 class="sec-title">外观</h2>

      <!-- 字体大小 -->
      <div class="row">
        <span class="row-label">字体大小</span>
        <div class="seg">
          <button
            v-for="f in (['small', 'medium', 'large'] as FontScale[])"
            :key="f"
            class="seg-btn"
            :class="{ on: s.fontScale === f }"
            @click="setFont(f)"
          >
            {{ f === "small" ? "小" : f === "medium" ? "中" : "大" }}
          </button>
        </div>
      </div>

      <!-- 手套模式 -->
      <div class="row">
        <span class="row-label">手套模式（更大按钮）</span>
        <label class="switch">
          <input type="checkbox" :checked="s.gloveMode" @change="(e) => setGlove((e.target as HTMLInputElement).checked)" />
          <span class="knob"></span>
        </label>
      </div>
    </section>

    <!-- 数据 -->
    <section class="card">
      <h2 class="sec-title"><AppIcon name="database" />数据</h2>
      <p class="sec-desc">
        所有数据只存本机，不上传云端。建议定期导出状态备份并另存。
        （实验记录功能已停用，备份不含实验内容）
      </p>
      <div class="btn-row">
        <button class="btn-main" @click="backupAll">导出状态备份（JSON）</button>
        <button class="btn" @click="pickImport">导入状态备份</button>
        <!-- 隐藏的文件选择器，由上面的按钮触发 -->
        <input
          ref="fileEl"
          type="file"
          accept="application/json,.json"
          hidden
          @change="onFilePicked"
        />
      </div>

      <!-- 导入前先给摘要：选错文件不至于直接覆盖现有数据 -->
      <div v-if="pendingImport" class="import-preview">
        <p class="import-head">
          将从 <b>{{ pendingImport.fileName }}</b> 导入
          <b>{{ importableCount(pendingImport.payload.localState) }}</b> 项状态
        </p>
        <p v-if="pendingImport.payload.exportedAt" class="import-meta">
          导出时间：{{ pendingImport.payload.exportedAt.replace("T", " ").slice(0, 19) }}
          <span v-if="pendingImport.payload.version"> · 版本 {{ pendingImport.payload.version }}</span>
        </p>
        <p class="import-warn">导入会覆盖当前同名的设置与收藏，确定吗？</p>
        <div class="btn-row">
          <button class="btn-main" @click="confirmImport">确认导入</button>
          <button class="btn" @click="pendingImport = null">取消</button>
        </div>
      </div>

      <p v-if="notice" class="notice">{{ notice }}</p>
    </section>

    <!-- 安全 -->
    <section class="card">
      <h2 class="sec-title"><AppIcon name="shield" />安全</h2>
      <button class="btn" @click="router.push('/safety')">查看安全应急手册</button>
    </section>

    <!-- 后端服务（P3） -->
    <section class="card">
      <h2 class="sec-title"><AppIcon name="server" />后端服务</h2>
      <p class="sec-desc">
        实验记录与化合物库由本地 Python 服务提供。应用启动时自动拉起，退出时自动回收；
        状态异常时可在此手动重启。
      </p>
      <div v-if="be" class="be-status">
        <span class="be-dot" :class="be.running ? 'ok' : 'bad'"></span>
        <span>
          {{ be.running ? "运行中" : "未就绪" }}
          <template v-if="be.base_url"> · {{ be.base_url }}</template>
          <template v-if="be.pid"> · PID {{ be.pid }}</template>
          <template v-if="be.version"> · v{{ be.version }}</template>
          <template v-if="be.reused"> · 复用已在运行的实例</template>
        </span>
      </div>
      <p v-if="be?.error" class="be-err">{{ be.error }}</p>
      <p v-if="be?.log_path" class="be-log">日志：{{ be.log_path }}</p>
      <div class="btn-row">
        <button class="btn" :disabled="beBusy" @click="doRestartBackend">
          {{ beBusy ? "重启中…" : "重启后端" }}
        </button>
        <button class="btn" :disabled="beBusy" @click="loadBackend">刷新状态</button>
      </div>
    </section>

    <!-- 关于 -->
    <section class="card">
      <h2 class="sec-title"><AppIcon name="info" />关于</h2>
      <p class="about">
        {{ APP_NAME }} v{{ APP_VERSION }}<br />
        私有实验室工具 · 离线可用 · 数据自主可控<br />
        技术栈：Tauri 2 + Vue 3 + TypeScript + SQLite
      </p>
    </section>

    <!-- 免责声明 -->
    <section class="card">
      <h2 class="sec-title"><AppIcon name="fileText" />免责声明</h2>
      <p class="disclaimer">
        本应用仅用于实验过程的记录、计算与提醒，不提供任何化学品合成步骤。
        SOP 内容由用户自行编写与负责。使用本应用时请遵守实验室安全规范，
        涉及危险化学品请务必遵循对应 SDS 与本单位规程。因使用本应用造成的
        任何后果，开发者不承担责任。详见 docs/免责声明.md。
      </p>
    </section>
  </div>
</template>

<style scoped>
.mine {
  max-width: 760px;
  margin: 0 auto;
}

.title {
  margin: 0 0 0.8rem;
  font-size: 1.3rem;
}

.card {
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  margin-bottom: 0.8rem;
}

.sec-title {
  margin: 0 0 0.6rem;
  font-size: 1rem;
  /* 图标 + 文字居中对齐（图标是 SVG，基线对齐会偏上） */
  display: flex;
  align-items: center;
  gap: 0.45rem;
  color: var(--text);
}
.sec-title :deep(.app-icon) {
  color: var(--primary);
}

.sec-desc {
  color: var(--muted);
  font-size: 0.85rem;
  margin: 0 0 0.6rem;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
}

.row:last-child {
  border-bottom: none;
}

.row-label {
  font-size: 0.95rem;
}

/* 分段选择器（字体/主题） */
.seg {
  display: flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.seg-btn {
  min-height: 38px;
  padding: 0 0.8rem;
  border: none;
  background-color: var(--bg);
  color: var(--text);
  font-size: 0.9rem;
  cursor: pointer;
}

.seg-btn.on {
  background-color: var(--primary-solid);
  color: #ffffff;
}

/* 开关（手套模式） */
.switch {
  position: relative;
  display: inline-block;
  width: 52px;
  height: 30px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.knob {
  position: absolute;
  inset: 0;
  background-color: var(--border);
  border-radius: 999px;
  transition: 0.2s;
}

.knob::before {
  content: "";
  position: absolute;
  left: 3px;
  top: 3px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: #ffffff;
  transition: 0.2s;
}

.switch input:checked + .knob {
  background-color: var(--ok);
}

.switch input:checked + .knob::before {
  transform: translateX(22px);
}

.btn-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.btn {
  min-height: 40px;
  padding: 0.2rem 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--bg);
  color: var(--text);
  font-size: 0.9rem;
  cursor: pointer;
}

.btn.danger {
  color: var(--danger);
  border-color: var(--danger-soft);
}

.btn-main {
  min-height: 42px;
  padding: 0.2rem 1rem;
  border: none;
  border-radius: 8px;
  background-color: var(--primary-solid);
  color: #ffffff;
  font-size: 0.95rem;
  cursor: pointer;
}

.about {
  font-size: 0.9rem;
  line-height: 1.8;
  margin: 0;
}

.notice {
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--ok);
  margin: 8px 0 0;
  word-break: break-all;
}

.disclaimer {
  font-size: 0.85rem;
  line-height: 1.7;
  color: var(--muted);
  margin: 0;
}

/* ---- 后端服务状态（P3）---- */
.be-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  line-height: 1.6;
  margin: 0 0 0.5rem;
}

.be-dot {
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  flex: 0 0 auto;
  background: var(--muted);
}

.be-dot.ok {
  background: #2e7d32;   /* 运行中：绿 */
}

.be-dot.bad {
  background: #c62828;  /* 未就绪：红 */
}

.be-err {
  font-size: 0.85rem;
  color: #c62828;
  margin: 0 0 0.5rem;
  word-break: break-all;
}

.be-log {
  font-size: 0.75rem;
  color: var(--muted);
  margin: 0 0 0.6rem;
  word-break: break-all;
}

/* 导入预览：橙色提示区，明确「会覆盖」这件事 */
.import-preview {
  margin-top: 0.8rem;
  padding: 0.8rem 0.9rem;
  border: 1px solid var(--warning);
  border-radius: var(--radius-sm);
  background-color: var(--warning-soft);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.import-head { margin: 0; font-size: 0.95rem; color: var(--text); }
.import-meta { margin: 0; font-size: 0.85rem; color: var(--muted); }
.import-warn { margin: 0; font-size: 0.85rem; color: var(--warning); font-weight: 600; }
.import-preview .btn-row { margin-top: 0.3rem; }
</style>
