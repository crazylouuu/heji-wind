// ============================================================
// sopSteps.ts —— 从 SOP 正文里提取"步骤"列表
// 步骤在 Markdown 里长这样（## 步骤 章节下的有序列表）：
//   ## 步骤
//   1. 加料
//   2. 加热
//   3. 终止
// 这个函数负责把它们解析成 [{ index, text }, ...]，
// 详情页才能渲染成可勾选的 checkbox 列表。
// ============================================================

export interface SopStep {
  /** 步骤编号（从 1 开始） */
  index: number;
  /** 步骤文字（去掉编号后的内容） */
  text: string;
}

/// 提取步骤列表；没有"步骤"章节时返回空数组
export function extractSteps(bodyMd: string): SopStep[] {
  const lines = bodyMd.split("\n");

  // 1. 找到 "## 步骤"（或 "### 步骤"）章节的起始行
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    if (/^#{2,3}\s*步骤/.test(lines[i].trim())) {
      start = i + 1;
      break;
    }
  }
  if (start === -1) return []; // 没有步骤章节：返回空

  // 2. 找到下一个 "## " 标题（步骤章节的结束边界）
  let end = lines.length;
  for (let i = start; i < lines.length; i++) {
    if (/^##\s/.test(lines[i].trim())) {
      end = i;
      break;
    }
  }

  // 3. 逐行匹配 "数字. 文字" 格式，收集步骤
  const steps: SopStep[] = [];
  for (let i = start; i < end; i++) {
    const m = lines[i].trim().match(/^(\d+)\.\s*(.+)$/);
    if (m) {
      steps.push({ index: parseInt(m[1], 10), text: m[2] });
    }
  }
  return steps;
}
