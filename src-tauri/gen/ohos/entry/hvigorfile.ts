import { hapTasks } from '@ohos/hvigor-ohos-plugin';
// OHOS 适配：注释掉 tauriPlugin 相关 import（Rust 已在命令行交叉编译，
// .so 已生成并放置，无需 hvigor 再次调用 cargo 编译）
// import { hvigor, HvigorPlugin, HvigorNode, HvigorTask } from '@ohos/hvigor';
// import { execFileSync } from 'child_process';
// import { resolve } from 'path';

export default {
  system: hapTasks,  /* Built-in plugin of Hvigor. It cannot be modified. */
  // plugins:[tauriPlugin()]   /* 已禁用：Rust 由命令行交叉编译（见 docs/鸿蒙构建.md） */
}

// function tauriPlugin(): HvigorPlugin {
//   return {
//     pluginId: 'tauri',
//     apply(node: HvigorNode) {
//       const buildRustCode = () => {
//         const properties = hvigor.getParameter().getProperties();
//         const target = properties.target || "aarch64";
//         execFileSync(`cargo`,
//           ["tauri", "ohos", "dev-eco-studio-script", "--target", target.toString()], {
//             cwd: resolve(__dirname, "../../../"),
//             stdio: "inherit",
//           });
//       }
//
//       node.getTaskByName('default@ConfigureCmake')!.afterRun(buildRustCode);
//     }
//   }
// }
