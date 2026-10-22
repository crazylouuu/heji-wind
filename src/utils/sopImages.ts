// ============================================================
// sopImages.ts —— SOP 插图加载（v2：base64 内嵌方案）
// 问题：Markdown 里 ![图](路线图.png) 生成的 <img src="相对路径">，
//       浏览器按"网页地址"解析，找不到文件系统里的文件。
// 方案 v3（当前）：走后端 HTTP `/api/sop/image` 取二进制，前端转 data URL。
//       相比 v2（Tauri invoke）的好处：浏览器模式（壳只当启动器）同样可用，
//       且不再依赖 Tauri 运行时；取数带 X-ChemLab-Token 头，
//       避免 `<img src>` 跨源时不带 cookie 导致图片时有时无。
// 类比：v1 是"告诉浏览器去本地哪取货"（依赖仓库大门开着）；
//       v2 是"让 Tauri 把货搬到 HTML 里"（只在壳里成立）；
//       v3 是"向同一台服务器的柜台取货"（谁都能取，规则一致）。
// ============================================================
import { apiDataUrl } from "./backend";

/// 把正文 HTML 里所有相对路径的 <img src> 替换成 base64 data URL
/// bodyHtml：marked 生成的 HTML；sopPath：md 文件的相对路径（如 "反应类型/xxx.md"）
/// 返回处理后的 HTML（没有图片时原样返回，零开销）
export async function resolveBodyImages(
  bodyHtml: string,
  sopPath: string,
): Promise<string> {
  // 正则快速检测：没有 <img> 标签直接返回（省一次异步 invoke）
  if (!/<img[^>]+src=/.test(bodyHtml)) return bodyHtml;

  // 图片相对路径的基准 = md 文件所在目录（去掉文件名部分）
  // 注意：Windows 下 entry.path 可能是反斜杠分隔（反应类型\xxx.md），
  // 统一转成正斜杠再按 "/" 切目录 —— 否则会把整个路径当文件名，找不到图！
  const normPath = sopPath.replace(/\\/g, "/");
  const dir = normPath.includes("/")
    ? normPath.slice(0, normPath.lastIndexOf("/"))
    : "";

  // 第一步：收集所有相对路径的图片引用（绝对 URL / data URL 不动）
  const rels: string[] = [];
  bodyHtml.replace(/src="([^"]+)"/g, (match, src: string) => {
    // 已经是完整地址（网络图、内嵌图）——不处理
    if (/^(https?:|data:|asset:|tauri:)/i.test(src)) return match;
    // marked 会对图片路径做 URL 编码（中文 → %E8%B7%AF...），
    // 必须用 decodeURIComponent 还原成真实文件名，否则 Rust 找不到文件！
    let real = src.replace(/^\.\//, ""); // 去掉 ./ 前缀
    try {
      real = decodeURIComponent(real); // 中文文件名还原（如 suzuki-路线图.png）
    } catch {
      // 非法编码：保持原样（极小概率，兜底）
    }
    rels.push(real);
    return match;
  });

  // 第二步：并行读取所有图片并转 base64（Promise.all 并发，互不等待）
  const dataUrls = await Promise.all(
    rels.map(async (rel) => {
      // 相对路径 → 以 md 所在目录为基准的完整相对路径（如 反应类型/路线图.png）
      const fullRel = dir ? `${dir}/${rel}` : rel;
      try {
        // 后端读文件并返回二进制，这里转成 data URL（后端有防路径穿越校验）
        return await apiDataUrl(`/api/sop/image?path=${encodeURIComponent(fullRel)}`);
      } catch (err) {
        // 单张图读失败：给空 src（显示裂图占位），绝不拖垮整篇正文。
        // 但必须把错误打出来 —— 教训：静默失败会掩盖根因，
        // 留一条 console.error 让开发者工具能看到（红色报错）。
        console.error("[SOP插图] 读取失败:", fullRel, err);
        return "";
      }
    }),
  );

  // 第三步：按顺序把相对路径 src 替换成 data URL
  let i = 0;
  return bodyHtml.replace(/src="([^"]+)"/g, (match, src: string) => {
    if (/^(https?:|data:|asset:|tauri:)/i.test(src)) return match;
    return `src="${dataUrls[i++]}"`;
  });
}
