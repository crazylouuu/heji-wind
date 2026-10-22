// ============================================================
// download.ts —— 文件导出的统一入口
//
// 原来导出走 Tauri 的 dialog（选路径）+ fs（写文件）。壳在启动器模式下
// 会退出、界面跑在浏览器里，这两个插件都不存在，所以统一改成
// 「浏览器下载」。壳窗口模式下也走同一条路 —— 少一条分支，少一种行为差异。
//
// 行为差异（可接受）：
//   原来：弹出保存对话框，用户选目录和文件名
//   现在：直接进浏览器下载目录（Chrome/Edge 可在设置里改成"每次询问"）
// ============================================================

/** 把文本内容作为文件下载（JSON / CSV / Markdown 都用它） */
export function downloadText(
  filename: string,
  text: string,
  mime = "text/plain;charset=utf-8",
): void {
  const blob = new Blob([text], { type: mime });
  downloadBlob(filename, blob);
}

/** 下载任意 Blob（PDF、图片等二进制） */
export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  // 必须挂到文档里才能在某些浏览器触发下载（Firefox 尤其）
  document.body.appendChild(a);
  a.click();
  a.remove();
  // 立刻 revoke 会让部分浏览器的下载中断，延迟释放
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** 生成带时间戳的文件名，如 合记ChemLab_状态备份_20261023-1502.json */
export function stampedName(base: string, ext: string): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  const stamp =
    `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}` +
    `-${p(d.getHours())}${p(d.getMinutes())}`;
  return `${base}_${stamp}.${ext}`;
}
