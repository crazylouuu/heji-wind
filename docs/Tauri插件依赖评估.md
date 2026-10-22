# Tauri 插件依赖评估：摘与不摘的实测结论

> 2026-10-23 ｜ 全部数据来自本机真实编译，不是估算

## 结论速览

| 插件 | Rust 侧调用 | 前端引用 | 处理 | 体积影响 |
| --- | --- | --- | --- | --- |
| `opener` | ✅ 启动器打开浏览器 | 0（用 Rust API） | **必须保留** | — |
| `notification` | 0 | 0（已改 Web Notification） | **已摘除** | −0.42 MB |
| `fs` | 0 | 仅休眠代码 | 保留 | −0.28 MB（若摘） |
| `dialog` | 0 | 仅休眠代码 | 保留 | −0.31 MB（若摘） |

**全摘 vs 保留的实测对比**：

| 状态 | exe 体积 | 相对原始 |
| --- | --- | --- |
| 原始（4 个插件） | 9.19 MB | — |
| 只摘 notification | **8.77 MB** | −0.42 MB |
| 全部摘掉（含 fs/dialog） | 8.18 MB | −1.01 MB（−11%） |

## 关键判断：为什么没全摘

省下 1.01 MB，但**安装包是 62.6 MB** —— 只占 1.6%。收益微乎其微。

而代价是实打实的：

1. **阻塞在休眠代码上**：`fs`/`dialog` 的 npm 包被 `src/components/ExperimentsPanel.vue`
   静态 import。该组件是 2026-09-23 停用「实验记录面板」后留下的休眠代码（无任何地方引用），
   但 `tsconfig` 会检查 `src/**`，删掉 npm 包 `vue-tsc` 立刻报找不到模块。
   要继续摘，得先处理这段代码（改动态 import 或移出 src）。
2. **版本校验必须两边同步**：Tauri CLI 校验 `@tauri-apps/plugin-x`（npm）与
   `tauri-plugin-x`（Cargo）的版本配对。只改一边会构建报错，所以每次都要动四个地方
   （Cargo.toml / lib.rs / capabilities / package.json + lockfile）。
3. **恢复成本**：注释里写明「恢复时只需把子 Tab/面板加回」，留着插件就是留着力气。

`notification` 不同 —— 前端与 Rust 两侧都已彻底不用，摘除没有任何阻碍，所以摘了。

## 摘掉插件的真实收益（不是体积）

| 维度 | 变化 |
| --- | --- |
| **权限面** | capabilities 少一项 `notification:default`（原 6 项 → 5 项） |
| **依赖树** | Cargo.lock 少一个 crate 及其子依赖，编译时间略降 |
| **代码诚实度** | 依赖列表里不再有「装了但没人用」的项，读代码时不会误以为通知走原生 |
| **体积** | −0.42 MB（对 62.6 MB 安装包无感） |

## 摘除一个插件的完整改动清单

以 notification 为例，**四处必须同步改**，漏一处就构建失败：

```
1. src-tauri/Cargo.toml          tauri-plugin-notification = "=2.4.0"   ← 删
2. src-tauri/src/lib.rs          .plugin(tauri_plugin_notification::init())  ← 删
3. src-tauri/capabilities/default.json   "notification:default"          ← 删
4. package.json                  "@tauri-apps/plugin-notification"       ← 删
   （并跑 pnpm install --lockfile-only 更新 pnpm-lock.yaml）
```

> 如果该插件还有自己的 scope 配置（`fs` 的 `"fs": [{...}]` 路径白名单），
> 也要一并删，否则配置里会残留一个指向不存在插件的字段。

## 功能影响：没有

摘掉 notification 后完整验证（真实启动）：

```
主壳 = 0（启动器模式已退出）
后端 = 1（PID 16220 独立存活）
/toolbox/ 200 · SOP 18 条
[ChemLab] 启动器模式：已打开 http://127.0.0.1:8765/toolbox/
```

计时器通知走浏览器 `Notification` API，与 Tauri 插件无关，所以摘除后行为不变。

## 什么时候才值得全摘

如果将来确定**不再恢复「实验记录面板」**，可以一次性清理：

1. 删除 `src/components/ExperimentsPanel.vue` + `src/utils/experiments.ts`
2. 删 Rust 侧 `db_*`（6 条）与 `export_pdf` 命令 + `printpdf` 依赖
3. 摘 `fs`/`dialog` 插件（四处同步）

预计 exe 可降到 **8.0 MB 以内**，同时清掉一批死代码。
但这是「代码清理」任务，收益主要在可维护性，不在体积。
