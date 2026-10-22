// ============================================================
// sop.ts —— SOP 数据的 TypeScript 类型定义
// 作用：定义"SOP 长什么样"的结构，让前后端都用同一套"图纸"。
// 类比：这是 SOP 的"合同模板"——Rust 后端按这个结构给数据，
//       前端按这个结构收数据，两边不会对不上。
// ============================================================

/// YAML frontmatter（文件头部元数据区）解析后的结构
/// 对应 docs/sop-schema.md 中的字段定义
export interface SopMeta {
  /** 唯一标识，如 alkylation-001 */
  id: string;
  /** 标题（列表页显示的名称） */
  title: string;
  /** 分类（对应 assets/sops 下的子目录名） */
  category: string;
  /** 标签数组（筛选和搜索用） */
  tags: string[];
  /** 风险等级：low / medium / high / critical / 待评估 */
  risk: string;
  /** 规模建议（可选） */
  scale?: string;
  /** 温度条件（可选） */
  temperature?: string;
  /** 预计时长（可选） */
  time?: string;
  /** 文献引用：只放 DOI / 链接（可选） */
  references?: string[];
}

/// 一条完整的 SOP
export interface Sop {
  /** 文件相对路径，如 "反应类型/烷基化.md"（含分类信息） */
  fileName: string;
  /** 元数据（来自 YAML frontmatter） */
  meta: SopMeta;
  /** 正文原始 Markdown（保留原样，便于导出） */
  bodyMd: string;
  /** 正文渲染后的 HTML（Day3 详情页展示用） */
  bodyHtml: string;
}

/// frontmatter 解析的中间形态：字段可能缺失，逐个兜底
/// （用户写的 SOP 偶尔漏字段，不能让整个解析崩溃）
export interface RawSopMeta extends Partial<SopMeta> {}

/// Rust 后端返回的文件列表项
export interface SopFileEntry {
  /** 相对路径（相对 assets/sops），如 "反应类型/烷基化.md" */
  path: string;
  /** 分类：从路径第一段推断，如 "反应类型" */
  category: string;
}
