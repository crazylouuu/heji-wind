<script setup lang="ts">
// ============================================================
// SafetyView.vue —— 安全应急页（Day7）
// 覆盖：泄漏 / 溅到 / 着火 / 废弃物 四类紧急情况
// 重要：此处只提供"通用应急原则"（防护、通风、疏散、报警、就医），
//       不包含任何具体化学品的处置步骤 —— 具体处置
//       必须查对应物质的 SDS 或本单位应急规程。
// 类比：这是贴在实验室墙上的"紧急情况一看就懂"大字报，
//       不是操作手册 —— 具体怎么处理，听消防/应急专业人士的。
// ============================================================
import { useRouter } from "vue-router";
import AppIcon, { type IconName } from "../components/AppIcon.vue";

const router = useRouter();

// 四类应急卡片的数据（只写通用框架）
// icon 用统一图标名（AppIcon），不再用 emoji —— emoji 在 Windows 上
// 彩色/单色混杂，四张卡片的视觉重量对不齐
const cards: { icon: IconName; title: string; color: string; steps: string[] }[] = [
  {
    icon: "wind",
    title: "化学品泄漏",
    color: "#f59e0b",
    steps: [
      "保持冷静，立即离开泄漏区域并疏散无关人员",
      "开窗通风，切断附近火源与电源",
      "戴好防护手套、护目镜，再考虑处置",
      "按本单位应急规程或物质 SDS 处理，必要时上报",
    ],
  },
  {
    icon: "droplet",
    title: "溅到身上",
    color: "#3b82f6",
    steps: [
      "皮肤：立即用大量清水持续冲洗至少 15 分钟",
      "眼睛：立即用洗眼器/清水冲洗，冲洗时睁眼转动眼球",
      "脱去被污染的衣物，避免继续接触",
      "记录接触的物质与时间，及时就医并带上信息",
    ],
  },
  {
    icon: "flame",
    title: "着火",
    color: "#ef4444",
    steps: [
      "立即报警（火警 119），并通知实验室负责人",
      "切断电源与气源，疏散人员",
      "小火可用灭火器处置；不明火情绝不盲目扑救，尤其不要用水",
      "人员受伤先撤离，救援交给专业消防",
    ],
  },
  {
    icon: "trash",
    title: "废弃物",
    color: "#10b981",
    steps: [
      "废弃物分类收集，不混装、不倒入下水道",
      "使用专用容器并贴标签（内容物、日期、危险类别）",
      "按实验室/单位的废弃物管理规定定期清运",
      "剧毒/危险废弃物交由有资质单位处理，绝不私自处置",
    ],
  },
];
</script>

<template>
  <div class="safety">
    <h1 class="title title-with-icon"><AppIcon name="shield" />安全应急</h1>

    <!-- 免责声明横幅（危险信息页必带） -->
    <div class="disclaimer">
      本页为<b>通用应急原则</b>，不针对任何具体化学品。具体物质的处置步骤，
      请以对应 <b>SDS（安全技术说明书）</b> 和本单位应急规程为准。
      紧急情况请先保证人身安全，再考虑其他。
    </div>

    <div class="grid">
      <section v-for="c in cards" :key="c.title" class="card">
        <h2 class="card-title" :style="{ borderColor: c.color }">
          <span class="card-icon"><AppIcon :name="c.icon" /></span> {{ c.title }}
        </h2>
        <ol class="steps">
          <li v-for="(s, i) in c.steps" :key="i">{{ s }}</li>
        </ol>
      </section>
    </div>

    <!-- 返回按钮 -->
    <button class="back-btn" @click="router.push('/mine')">← 返回设置</button>
  </div>
</template>

<style scoped>
.safety {
  max-width: 760px;
  margin: 0 auto;
}

.title {
  margin: 0 0 0.8rem;
  font-size: 1.3rem;
}

.disclaimer {
  background-color: var(--danger-soft);
  border: 1px solid var(--danger);
  border-radius: var(--radius-sm);
  padding: 0.8rem;
  font-size: 0.9rem;
  color: var(--danger);
  margin-bottom: 1rem;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.8rem;
}

@media (max-width: 640px) {
  .grid {
    grid-template-columns: 1fr;
  }
}

.card {
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
}

.card-title {
  margin: 0 0 0.6rem;
  font-size: 1.05rem;
  border-left: 4px solid var(--border);
  padding-left: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.steps {
  margin: 0;
  padding-left: 1.2rem;
  font-size: 0.9rem;
  line-height: 1.7;
}

.back-btn {
  min-height: 44px;
  margin-top: 1rem;
  padding: 0.2rem 1.2rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background-color: var(--card);
  color: var(--text);
  font-size: 0.95rem;
  cursor: pointer;
}

/* 场景图标：线性 SVG，跟随标题文字色；比 emoji 更可控 */
.card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  vertical-align: -5px;
  margin-right: 6px;
  color: var(--primary);
}
.card-icon :deep(.app-icon) {
  width: 20px;
  height: 20px;
}

/* 页面标题图标：与标题文字居中对齐 */
.title-with-icon {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.title-with-icon :deep(.app-icon) {
  color: var(--primary);
}

</style>
