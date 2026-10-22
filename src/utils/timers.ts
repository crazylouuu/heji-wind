// ============================================================
// timers.ts —— 多计时器的状态管理与持久化（Day 6）
// 核心设计：用"目标结束时间戳"而不是"剩余秒数递减"。
// 为什么？WebView 最小化/后台时 setInterval 可能被节流，
// 但系统时钟（Date.now()）永远准确——恢复时用时间戳一算，
// 剩余时间一点不差（就像微波炉：靠"设定的停止时刻"计时，
// 而不是"每过一秒减一秒"）。
// ============================================================
// 通知改用浏览器 Web Notification API（2026-10-23）：
//   壳在启动器模式下会退出，界面跑在浏览器里，Tauri 的通知插件不可用。
//   Notification API 在 localhost / 127.0.0.1 属于 secure context，可以直接用。
//   限制：页面必须开着才收得到（浏览器不给关闭的页面推通知）—— 这是浏览器
//   的固有限制，不是本应用的缺陷。

/** 一个计时器的状态 */
export interface TimerState {
  id: string;             // 唯一标识（生成随机串）
  name: string;           // 名称（如 "冰浴搅拌"）
  totalSec: number;       // 设定总时长（秒）
  endAt: number | null;   // 运行中：目标结束时间戳（毫秒）；null = 不在运行
  pausedRemainSec: number; // 暂停时保存的剩余秒数（用于恢复）
}

/** 存储键 */
const KEY = "heji_timers";

// ---------- 持久化 ----------

/// 读出所有计时器（数据损坏时返回空数组）
export function loadTimers(): TimerState[] {
  try {
    const arr = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

/// 保存所有计时器
export function saveTimers(timers: TimerState[]): void {
  localStorage.setItem(KEY, JSON.stringify(timers));
}

// ---------- 状态计算 ----------

/// 剩余秒数：运行中 = (结束时刻 - 现在)/1000；暂停 = 保存值
export function remainingSec(t: TimerState, now = Date.now()): number {
  if (t.endAt !== null) {
    return Math.max(0, Math.round((t.endAt - now) / 1000));
  }
  return t.pausedRemainSec;
}

/// 是否在运行
export function isRunning(t: TimerState): boolean {
  return t.endAt !== null;
}

/// 开始/继续：把"剩余秒数"换算成"结束时间戳"存下来
export function startTimer(t: TimerState, now = Date.now()): TimerState {
  return { ...t, endAt: now + remainingSec(t, now) * 1000 };
}

/// 暂停：把剩余秒数存进 pausedRemainSec，endAt 置空
export function pauseTimer(t: TimerState, now = Date.now()): TimerState {
  return { ...t, endAt: null, pausedRemainSec: remainingSec(t, now) };
}

/// 重置：回到初始总时长
export function resetTimer(t: TimerState): TimerState {
  return { ...t, endAt: null, pausedRemainSec: t.totalSec };
}

/// 生成唯一 id（时间戳 + 随机数，够用即可）
export function newId(): string {
  return `${Date.now()}-${Math.floor(Math.random() * 10000)}`;
}

/// 秒 → "mm:ss" 显示格式
export function fmtTime(totalSec: number): string {
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// ---------- 通知 ----------

/// 浏览器是否支持通知（老环境 / 非 secure context 会没有 Notification）
function notifySupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

/// 确保通知权限已授予（首次会弹系统授权请求）
///
/// 注意：requestPermission 必须在用户手势（点击等）里调用，否则部分浏览器
/// 会直接判定为 denied。所以计时器启动时的点击是最好的时机。
export async function ensureNotifyPermission(): Promise<boolean> {
  if (!notifySupported()) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false; // 已被永久拒绝，不再烦用户
  try {
    const r = await Notification.requestPermission();
    return r === "granted";
  } catch {
    return false;
  }
}

/// 发送"计时完成"通知；不可用时退回「标题闪烁」提醒
export function notifyDone(name: string): void {
  const title = "计时完成";
  const body = `「${name}」时间到！`;

  if (notifySupported() && Notification.permission === "granted") {
    try {
      const n = new Notification(title, { body, tag: `timer-${name}` });
      // 点通知回到应用
      n.onclick = () => {
        window.focus();
        n.close();
      };
      return;
    } catch {
      /* 某些环境构造失败，走下面的降级 */
    }
  }

  // 降级：改标题引起注意，并在控制台留痕（不阻塞、不弹 alert ——
  // 计时是后台行为，弹窗会把用户正在做的事打断）
  flashTitle(body);
}

/// 标题闪烁约 10 秒：没有通知权限时的兜底提醒
function flashTitle(body: string): void {
  if (typeof document === "undefined") return;
  const original = document.title;
  let on = false;
  let n = 0;
  // 每 800ms 切一次，切 12 次（约 10 秒）后恢复
  const t = setInterval(() => {
    document.title = on ? original : `⏰ ${body}`;
    on = !on;
    if (++n >= 12) {
      clearInterval(t);
      document.title = original;
    }
  }, 800);
  // 用户切回来就停止闪烁
  const stop = () => {
    clearInterval(t);
    document.title = original;
    window.removeEventListener("focus", stop);
  };
  window.addEventListener("focus", stop);
}
