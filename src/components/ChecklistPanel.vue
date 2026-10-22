<script setup lang="ts">
// ============================================================
// ChecklistPanel.vue —— 实验检查清单组件（Day 6）
// 预设 5 组通用提醒（无水无氧/低温/氢化/柱层析/放大），
// 支持勾选、新增自定义项、删除自定义项；状态存 localStorage。
// 内容仅为通用操作提醒，不含具体危险化学品操作步骤。
// ============================================================
import { computed, ref } from "vue";
import {
  type ChecklistItem,
  loadItems,
  saveItems,
  addItem,
  toggleItem,
  removeItem,
} from "../utils/checklist";

// 全部检查项（从 localStorage 恢复，含预设和自定义）
const items = ref<ChecklistItem[]>(loadItems());

// 自定义项输入
const newText = ref("");
const newGroup = ref("自定义");

// 分组（保持预设顺序）
const groups = computed(() => {
  const seen: string[] = [];
  for (const i of items.value) {
    if (!seen.includes(i.group)) seen.push(i.group);
  }
  return seen;
});

// 某组的项
function groupItems(group: string) {
  return items.value.filter((i) => i.group === group);
}

// 某组完成数（进度提示）
function groupDone(group: string) {
  const g = groupItems(group);
  return g.filter((i) => i.checked).length;
}

// 勾选
function onToggle(id: string) {
  items.value = toggleItem(items.value, id);
  saveItems(items.value);
}

// 删除（自定义项）
function onRemove(id: string) {
  items.value = removeItem(items.value, id);
  saveItems(items.value);
}

// 新增自定义项
function onAdd() {
  const text = newText.value.trim();
  if (!text) return;
  items.value.push(addItem(newGroup.value, text));
  saveItems(items.value);
  newText.value = "";
}
</script>

<template>
  <div class="checklist">
    <!-- 新增自定义项 -->
    <div class="add-row">
      <input v-model="newText" class="in-text" placeholder="新增检查项（如：确认天平校准）" />
      <input v-model="newGroup" class="in-group" placeholder="分组（默认 自定义）" />
      <button class="btn-add" @click="onAdd">添加</button>
    </div>

    <!-- 分组列表 -->
    <section v-for="g in groups" :key="g" class="group">
      <h3 class="g-title">
        {{ g }}
        <span class="g-progress">{{ groupDone(g) }}/{{ groupItems(g).length }}</span>
      </h3>
      <label v-for="i in groupItems(g)" :key="i.id" class="item" :class="{ done: i.checked }">
        <input
          type="checkbox"
          class="ck"
          :checked="i.checked"
          @change="onToggle(i.id)"
        />
        <span class="text">{{ i.text }}</span>
        <!-- 自定义项才显示删除按钮 -->
        <button v-if="i.id.startsWith('c-')" class="del" @click="onRemove(i.id)">✕</button>
      </label>
    </section>

    <p v-if="items.length === 0" class="empty">还没有检查项</p>
  </div>
</template>

<style scoped>
.add-row {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.8rem;
}

.in-text {
  flex: 1;
  min-height: 44px;
  padding: 0.4rem 0.8rem;
  font-size: 0.95rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--bg);
  color: var(--text);
}

.in-group {
  width: 6rem;
  min-height: 44px;
  padding: 0.4rem 0.5rem;
  font-size: 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--bg);
  color: var(--text);
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

.group {
  margin-bottom: 0.8rem;
}

.g-title {
  font-size: 0.95rem;
  margin: 0.8rem 0 0.4rem;
  color: var(--muted);
  border-left: 3px solid var(--primary);
  padding-left: 0.5rem;
  display: flex;
  justify-content: space-between;
}

.g-progress {
  font-size: 0.8rem;
  color: var(--ok);
}

.item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.4rem;
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-bottom: 0.4rem;
  cursor: pointer;
  min-height: 44px;
}

.item.done .text {
  text-decoration: line-through;
  color: var(--muted);
}

.ck {
  width: 20px;
  height: 20px;
  accent-color: var(--ok);
}

.text {
  flex: 1;
  font-size: 0.95rem;
}

.del {
  background: none;
  border: none;
  color: var(--danger);
  font-size: 1rem;
  cursor: pointer;
  padding: 0.2rem 0.5rem;
}

.empty {
  color: var(--muted);
  text-align: center;
  padding: 1rem 0;
  font-size: 0.9rem;
}
</style>
