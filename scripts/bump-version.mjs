#!/usr/bin/env node
// ============================================================
// bump-version.mjs —— 一条命令同步所有位置的版本号并打 tag
//
// 为什么需要它：版本号散在两处（package.json 和 src-tauri/tauri.conf.json），
// Tauri CLI 会校验两者是否一致，不一致直接终止构建。手动改容易漏，
// 改完还得记得打 tag —— 这个脚本把三件事一次做完。
//
// 用法：
//   node scripts/bump-version.mjs 1.0.0     # 写入并打 tag v1.0.0
//   node scripts/bump-version.mjs 1.0.1 --dry-run   # 只看会改什么，不动文件
//   node scripts/bump-version.mjs --show    # 显示当前版本
//
// 打 tag 但不 push —— 推不推、什么时候推由你决定。
// ============================================================

import { readFileSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const FILES = [
  { path: join(ROOT, "package.json"), kind: "json", key: "version" },
  { path: join(ROOT, "src-tauri", "tauri.conf.json"), kind: "json", key: "version" },
];

/// 语义化版本：MAJOR.MINOR.PATCH，允许 -prerelease 和 +build
const SEMVER = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const show = args.includes("--show");
const target = args.find((a) => !a.startsWith("--"));

function readVersion(file) {
  const data = JSON.parse(readFileSync(file.path, "utf8"));
  return data[file.key];
}

if (show || !target) {
  console.log("\n当前版本：");
  for (const f of FILES) {
    const rel = f.path.slice(ROOT.length + 1);
    console.log(`  ${rel.padEnd(28)} ${readVersion(f)}`);
  }
  if (!show) {
    console.log("\n用法：node scripts/bump-version.mjs <新版本号> [--dry-run]");
    console.log("例：  node scripts/bump-version.mjs 1.0.0\n");
  }
  process.exit(0);
}

if (!SEMVER.test(target)) {
  console.error(`\n版本号格式不对：${target}`);
  console.error("要求 主.次.修订，例：1.0.0 / 1.2.3 / 2.0.0-beta.1\n");
  process.exit(1);
}

// 一致性检查：改之前先看两处是否已经同步，不同步说明有人手改过
const before = FILES.map(readVersion);
if (new Set(before).size > 1) {
  console.warn("\n⚠️  注意：改动前两处版本号已经不一致：");
  FILES.forEach((f, i) => console.warn(`     ${f.path.slice(ROOT.length + 1)}: ${before[i]}`));
  console.warn("   这会导致 tauri build 失败，本脚本会把它们统一成新版本。\n");
}

console.log(`\n${dryRun ? "[演练] " : ""}版本号 → ${target}\n`);

for (const f of FILES) {
  const rel = f.path.slice(ROOT.length + 1);
  const raw = readFileSync(f.path, "utf8");
  const data = JSON.parse(raw);
  const old = data[f.key];
  data[f.key] = target;

  // 保留原文件的缩进（package.json 用 2 空格，tauri.conf.json 也是）
  const indent = raw.match(/^\{\s*\n(\s+)/)?.[1]?.length ?? 2;
  const next = JSON.stringify(data, null, indent) + "\n";

  if (dryRun) {
    console.log(`  ${rel.padEnd(28)} ${old} → ${target}  (未写入)`);
  } else {
    writeFileSync(f.path, next, "utf8");
    console.log(`  ${rel.padEnd(28)} ${old} → ${target}`);
  }
}

const tag = `v${target}`;

// 检查 tag 是否已存在
let tagExists = false;
try {
  execSync(`git rev-parse ${tag}`, { cwd: ROOT, stdio: "pipe" });
  tagExists = true;
} catch {
  /* 不存在，正常 */
}

if (dryRun) {
  console.log(`\n[演练] 将会创建 tag：${tag}${tagExists ? "  (已存在，跳过)" : ""}\n`);
  process.exit(0);
}

if (tagExists) {
  console.log(`\n  tag ${tag} 已存在，不重复创建。\n`);
} else {
  try {
    execSync(`git add ${FILES.map((f) => `"${f.path}"`).join(" ")}`, { cwd: ROOT, stdio: "pipe" });
    execSync(`git commit -m "chore: 版本号 ${before[0]} → ${target}"`, { cwd: ROOT, stdio: "pipe" });
    execSync(`git tag -a ${tag} -m "${tag}"`, { cwd: ROOT, stdio: "pipe" });
    console.log(`\n  已提交并打 tag：${tag}`);
  } catch (err) {
    console.error("\n  提交或打 tag 失败：", err.message);
    console.error("  文件已改好，请手动提交。\n");
    process.exit(1);
  }
}

console.log(`
下一步：
  git push && git push --tags     推上去
  powershell -ExecutionPolicy Bypass -File build/build.ps1 -Fast     打包
  然后在 GitHub 建 Release，上传安装包
`);
