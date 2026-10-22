<script setup lang="ts">
// ============================================================
// TimerList.vue —— 多计时器组件（Day 6）
// 功能：命名、倒计时、开始/暂停/重置/删除、到点本地通知。
// 原理：每秒 tick 一次刷新界面；剩余时间按"结束时间戳"计算
//       （后台/最小化也不漂移）；到点发系统通知并自动停止。
// ============================================================
import { onMounted, onUnmounted, ref } from "vue";
import {
  type TimerState,
  loadTimers,
  saveTimers,
  remainingSec,
  isRunning,
  startTimer,
  pauseTimer,
  resetTimer,
  newId,
  fmtTime,
  ensureNotifyPermission,
  notifyDone,
} from "../utils/timers";

// 计时器列表（从 localStorage 恢复）
const timers = ref<TimerState[]>(loadTimers());

// 新增表单
const newName = ref("");
const newMin = ref<number>(5);
const newSec = ref<number>(0);

// tick 计数：每秒 +1，触发界面重新渲染剩余时间
const tick = ref(0);
let interval: number | undefined;

onMounted(() => {
  // 每秒：刷新显示 + 检查有没有到点的计时器
  interval = window.setInterval(() => {
    tick.value++;
    checkExpired();
  }, 1000);
});

onUnmounted(() => {
  window.clearInterval(interval); // 组件销毁时停掉定时器，防内存泄漏
});

// 检查到点：剩余 0 且还在运行 → 发通知 + 自动停止
function checkExpired() {
  for (let i = 0; i < timers.value.length; i++) {
    const t = timers.value[i];
    if (isRunning(t) && remainingSec(t) === 0) {
      notifyDone(t.name);
      timers.value[i] = { ...t, endAt: null, pausedRemainSec: 0 };
      saveTimers(timers.value);
    }
  }
}

// 新增一个计时器
function addTimer() {
  const total = (newMin.value || 0) * 60 + (newSec.value || 0);
  if (total <= 0) return; // 时长必须 > 0
  timers.value.push({
    id: newId(),
    name: newName.value.trim() || "计时器",
    totalSec: total,
    endAt: null,
    pausedRemainSec: total,
  });
  saveTimers(timers.value);
  newName.value = "";
  newMin.value = 5;
  newSec.value = 0;
}

// 开始（首次会请求系统通知权限）
async function onStart(t: TimerState) {
  await ensureNotifyPermission(); // 授权失败也不阻止计时
  const i = timers.value.indexOf(t);
  timers.value[i] = startTimer(t);
  saveTimers(timers.value);
}

// 暂停
function onPause(t: TimerState) {
  const i = timers.value.indexOf(t);
  timers.value[i] = pauseTimer(t);
  saveTimers(timers.value);
}

// 重置
function onReset(t: TimerState) {
  const i = timers.value.indexOf(t);
  timers.value[i] = resetTimer(t);
  saveTimers(timers.value);
}

// 删除
function onDelete(t: TimerState) {
  timers.value = timers.value.filter((x) => x.id !== t.id);
  saveTimers(timers.value);
}
</script>

<template>
  <div class="timers">
    <!-- 新增表单 -->
    <div class="add-row">
      <input v-model="newName" class="in-name" placeholder="名称（如 冰浴搅拌）" />
      <input v-model.number="newMin" class="in-num" type="number" min="0" placeholder="分" />
      <span class="colon">:</span>
      <input v-model.number="newSec" class="in-num" type="number" min="0" max="59" placeholder="秒" />
      <button class="btn-add" @click="addTimer">添加</button>
    </div>

    <!-- 计时器列表 -->
    <div v-if="timers.length === 0" class="empty">还没有计时器，上面添加一个</div>

    <div v-for="t in timers" :key="t.id" class="timer-card" :class="{ running: isRunning(t) }">
      <div class="t-head">
        <span class="t-name">{{ t.name }}</span>
        <span class="t-state">{{ isRunning(t) ? "⏳ 运行中" : "⏸ 已停止" }}</span>
      </div>

      <!-- 剩余时间大字显示（tick 驱动每秒刷新） -->
      <div class="t-time">{{ fmtTime(remainingSec(t)) }}</div>

      <div class="t-btns">
        <button v-if="!isRunning(t)" class="btn" @click="onStart(t)">▶ 开始</button>
        <button v-else class="btn" @click="onPause(t)">⏸ 暂停</button>
        <button class="btn" @click="onReset(t)">↺ 重置</button>
        <button class="btn danger" @click="onDelete(t)">✕ 删除</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.add-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.8rem;
}

.in-name {
  flex: 1;
  min-height: 44px;
  padding: 0.4rem 0.8rem;
  font-size: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--bg);
  color: var(--text);
}

.in-num {
  width: 4.5rem;
  min-height: 44px;
  padding: 0.4rem 0.5rem;
  font-size: 1rem;
  text-align: center;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--bg);
  color: var(--text);
}

.colon {
  font-size: 1.1rem;
  color: var(--muted);
}

.btn-add {
  min-height: 44px;
  padding: 0.3rem 1rem;
  border-radius: 8px;
  border: none;
  background-color: var(--primary-solid);
  color: #ffffff;
  font-size: 0.95rem;
  cursor: pointer;
  white-space: nowrap;
}

.empty {
  color: var(--muted);
  text-align: center;
  padding: 1.5rem 0;
  font-size: 0.9rem;
}

.timer-card {
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.9rem 1rem;
  margin-bottom: 0.6rem;
}

/* 运行中的计时器：边框高亮 */
.timer-card.running {
  border-color: var(--primary);
}

.t-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.t-name {
  font-weight: 600;
}

.t-state {
  font-size: 0.8rem;
  color: var(--muted);
}

.t-time {
  font-size: 2.2rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--primary);
  text-align: center;
  padding: 0.3rem 0;
}

.t-btns {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
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
</style>
