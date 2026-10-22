# 变更日志

本项目的所有重要变更都记在这里。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增

- 设置页支持**导入**状态备份（原来只能导出，换电脑时备份文件没用）
- 导入前先显示摘要（项数、导出时间、覆盖警告），确认后才写入
- 只导入 `heji_` 前缀的键，避免把别人文件的无关数据灌进来
- `DESIGN.md` 视觉规范，含双前端变量名映射表
- `docs/UI审计报告.md` 与 `docs/换电脑迁移清单.md`

### 变更

- 导航从顶部横条改为**左侧竖栏**，按「工作台 / 工具 / 实验 / 设置」分组
- 全站 emoji 图标换成内联 SVG（17 个），线条与尺寸统一
- 主色拆成三个用途明确的 token，修掉对比度不达标问题
- 安装包体积 **62.6 MB → 47.2 MB**
- 构建改用 npm（pnpm 在 Windows 上建不了 node_modules 符号链接）
- 发布不再做代码签名

### 移除

- **深色模式**（电脑端实验室工具，环境光照稳定，多维护一套主题不划算）
- **应用锁**（纯前端明文 PIN，F12 三秒可绕，属误导性安全功能）
- **Ketcher 结构式画板**（占 30 MB；结构式改由输入 SMILES 或粘贴 Molfile 后 RDKit 渲染成图）
- Rust 侧整套旧的实验记录实现（13 个 Tauri 命令 + db.rs + models.rs，前端已全部改走 HTTP API）
- 依赖：rusqlite、printpdf、chrono、tauri-plugin-fs、tauri-plugin-dialog

### 修复

- **静态文件没有缓存头**：更新后浏览器仍显示旧界面，必须 Ctrl+F5 才能看到新版
- **8 处文字对比度不达标**（最低 2.61:1），现全部满足 WCAG AA 4.5:1
- **NSIS 升级安装不清理旧文件**：删掉的资源仍占 31 MB 磁盘
- 后端 sidecar 精简：删掉 rdkit/Contrib、rdkit/sping、PIL 的 AVIF 解码器

---

## [0.11.2] - 2026-10-23

此前为内部迭代阶段，主要工作是把三个独立应用（合成工具箱、合迹 ChemELN、
黄河 ChemELN 的数据）整合为单一工作台，并把 Tauri 壳降级为启动器。

> 注：`0.x` 阶段不给 API 兼容性承诺。首个公开版本将发布为 `1.0.0`。
