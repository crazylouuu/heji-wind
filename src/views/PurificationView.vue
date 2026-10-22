<script setup lang="ts">
// ============================================================
// PurificationView.vue —— 纯化操作（首页快捷入口 → 独立页）
// 2026-09-24 新增：常见纯化方法的知识框架卡片
// 每张卡片：原理 / 适用场景 / 关键要点 / 安全注意
// 内容为通用操作知识框架（不包含任何具体危险化学品操作步骤），
// 详细 SOP 由用户自行在 SOP 库中补充填写。
// ============================================================

// 纯化方法列表（纯数据，渲染成卡片）
const methods = [
  {
    name: "重结晶",
    principle: "利用溶质在不同温度下溶解度差异：高温溶解 → 缓慢降温 → 晶体析出，杂质留在母液。",
    use: "固体粗产物的纯度提升；适合 50 mg 以上的固体样品。",
    points: [
      "溶剂选择：目标物热溶冷析明显、杂质溶解度差异大",
      "热过滤除去不溶物（趁热，防止析出）",
      "缓慢降温 + 静置，晶体才规则",
      "母液浓缩可回收第二批晶体（纯度可能下降）",
    ],
    safety: "加热时防暴沸；可燃溶剂远离火源；操作在通风处进行。",
  },
  {
    name: "柱层析（快速柱）",
    principle: "混合物沿固定相（硅胶）移动，各组分与硅胶吸附力不同而分速不同，先后被洗脱。",
    use: "实验室最通用的纯化手段；毫克到克级均可。",
    points: [
      "装柱要实、上样要平（干法/湿法上样）",
      "洗脱梯度从弱到强（如 PE→PE/EtOAc 梯度）",
      "点板（TLC）确定目标物 Rf 与合适洗脱剂比例",
      "目标 Rf 在 0.2–0.35 附近分离最好",
    ],
    safety: "大量可燃洗脱剂，远离火源；溶剂蒸气注意通风。",
  },
  {
    name: "蒸馏 / 减压蒸馏",
    principle: "利用沸点差异分离液体：加热使低沸点组分先汽化、冷凝收集。",
    use: "液体产物或溶剂的纯化；减压蒸馏降低沸点保护热不稳定物。",
    points: [
      "加沸石防暴沸（减压前必须补加）",
      "减压蒸馏前检查体系气密性",
      "收集不同馏分分别标识",
      "高沸点/热不稳定物优先考虑减压",
    ],
    safety: "减压体系防炸裂（用厚壁瓶/保护挡板）；蒸馏可燃物远离火源；密闭体系泄压慢开。",
  },
  {
    name: "萃取 / 洗涤",
    principle: "利用溶质在两相（有机/水）中分配系数不同，把目标物转入所需相。",
    use: "反应后处理最常用；去除水溶性杂质或酸碱性杂质。",
    points: [
      "先判断目标物在有机相还是水相（酸碱性、极性）",
      "分液漏斗放气要多次、朝安全方向",
      "水相用饱和食盐水洗可减少乳化",
      "有机相合并后必须干燥（无水硫酸钠/硫酸镁）再浓缩",
    ],
    safety: "分液时及时放气防喷溅；戴手套，避免溶剂接触皮肤。",
  },
  {
    name: "过滤与干燥",
    principle: "固液分离（常压/减压抽滤），固体再用合适方式干燥除去残留溶剂。",
    use: "收集沉淀/结晶产物；干燥后称量、表征。",
    points: [
      "抽滤用滤纸/砂芯，先用少量溶剂润湿",
      "洗涤固体用少量冷溶剂，避免溶解损失",
      "干燥方式：空气、真空干燥器、烘箱（看产物热稳定性）",
      "干燥前后称重，确认溶剂去除",
    ],
    safety: "烘箱干燥易燃物前确认无残留可燃溶剂；真空干燥注意温度上限。",
  },
  {
    name: "薄层色谱（TLC）",
    principle: "微量样品在硅胶薄板上随展开剂移动，用 Rf 值判断纯度与极性，是柱层析的「侦察兵」。",
    use: "监控反应进度、确定柱层析洗脱剂、判断纯度。",
    points: [
      "点样量要少（细点），展开缸内饱和",
      "紫外灯 / 碘缸 / 高锰酸钾显色",
      "产物应与标样 Rf 一致且无杂点",
    ],
    safety: "展开剂含可燃溶剂，远离火源；碘蒸气注意通风。",
  },
];
</script>

<template>
  <div class="pur">
    <h1 class="title">纯化操作</h1>
    <p class="hint">
      常用纯化方法知识框架（原理 → 适用 → 要点 → 安全）。
      详细 SOP 请在 SOP 库中自行补充；本页为通用方法导航。
    </p>

    <!-- 方法卡片 -->
    <div class="grid">
      <section v-for="m in methods" :key="m.name" class="card">
        <h2>{{ m.name }}</h2>
        <p class="p"><b>原理：</b>{{ m.principle }}</p>
        <p class="p"><b>适用：</b>{{ m.use }}</p>
        <ul class="pts">
          <li v-for="(pt, i) in m.points" :key="i">{{ pt }}</li>
        </ul>
        <p class="safe"><b>安全注意：</b>{{ m.safety }}</p>
      </section>
    </div>

    <p class="footnote">内容为通用知识框架，具体操作请结合受训经验与你的 SOP 文档执行</p>
  </div>
</template>

<style scoped>
.pur {
  max-width: 900px;
  margin: 0 auto;
}

.title {
  margin: 0 0 0.8rem;
  font-size: 1.3rem;
}

.hint {
  color: var(--muted);
  font-size: 0.9rem;
  margin: 0 0 0.8rem;
}

/* 卡片：2 列网格 */
.grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.8rem;
}

.card {
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
}

.card h2 {
  margin: 0 0 0.6rem;
  font-size: 1.05rem;
  color: var(--primary);
}

.p {
  font-size: 0.88rem;
  margin: 0 0 0.5rem;
  line-height: 1.5;
}

.pts {
  margin: 0 0 0.6rem;
  padding-left: 1.2rem;
  font-size: 0.85rem;
  line-height: 1.55;
}

.safe {
  font-size: 0.85rem;
  margin: 0;
  padding: 0.5rem 0.7rem;
  border-radius: 8px;
  background-color: var(--danger-soft);
  color: var(--danger);
  line-height: 1.5;
}

.footnote {
  text-align: center;
  color: var(--muted);
  font-size: 0.8rem;
  margin-top: 1.2rem;
}
</style>
