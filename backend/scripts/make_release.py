# -*- coding: utf-8 -*-
"""生成可发布的 release/ 目录（用于上传 GitHub）。

排除内容（重要）：
  - backend/data            真实实验数据（绝不上传）
  - backend/venv            本机虚拟环境（体积大、不可移植）
  - private/                内部与商业化设计文档
  - push_to_github.bat      含本机绝对路径
  - docs/purification-book-distill.html   第三方书籍版权内容

安全检查：只允许删除并重建 <项目根>/release，路径不符直接中止。
所有判断与文件操作都在本脚本，make_release.bat 只是薄壳。

用法：
    backend\\venv\\Scripts\\python backend\\scripts\\make_release.py
    backend\\venv\\Scripts\\python backend\\scripts\\make_release.py --check   只校验不生成
"""
import argparse
import fnmatch
import os
import shutil
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REL = os.path.join(ROOT, "release")

# 目录：整棵不复制
IGNORE_DIRS = {"data", "venv", "__pycache__", ".pytest_cache", ".git",
               "node_modules", "private", "release", "backups"}
# 文件：按名称/通配排除
IGNORE_PATTERNS = ["*.log", "*.pyc", "*.pyo", "*.db", "*.zip",
                   "push_to_github.bat", "purification-book-distill.html", "nul"]

# 需要整棵复制到 release 的目录
TREES = ["backend", "frontend", "docs"]
# 需要复制到 release 根目录的单个文件
ROOT_FILES = [
    "README.md", "CHANGELOG.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "RELEASING.md",
    ".gitignore", "start_windows.bat", "start_backend.bat",
    "start_backend_hidden.vbs", "install.bat", "uninstall.bat",
    "backup_now.bat", "setup_shortcuts.vbs", "安全备份.bat", "诊断.bat",
    "重启服务.bat",
    # 打包工程（v1.2.0 起）：PyInstaller onedir 绿色版
    "ChemELN.spec", "build.ps1", "scripts",
]

# 生成后必须不存在的路径（自检用）
FORBIDDEN = [
    os.path.join("backend", "data"),
    os.path.join("backend", "venv"),
    "private",
    "push_to_github.bat",
    os.path.join("docs", "purification-book-distill.html"),
]

# 生成后必须存在的关键文件（防漏，尤其图片等易被误加进排除规则的资源）
REQUIRED = [
    "CHANGELOG.md",
    "ChemELN.spec",
    os.path.join("frontend", "index.html"),
    os.path.join("frontend", "img", "logo.ico"),
    os.path.join("frontend", "img", "logo.png"),
    os.path.join("frontend", "img", "logo-192.png"),
    os.path.join("frontend", "js", "view-experiments.js"),
    os.path.join("backend", "main.py"),
    os.path.join("backend", "config.py"),
    os.path.join("backend", "migrations.py"),
    os.path.join("backend", "utils", "code_fingerprint.py"),
    "start_windows.bat",
    "install.bat",
    "诊断.bat",
    "重启服务.bat",
]


def safe_target() -> str:
    """校验 release 路径，防止误删项目其它目录。"""
    real = os.path.realpath(REL)
    root_real = os.path.realpath(ROOT)
    if os.path.basename(real) != "release" or not real.startswith(root_real + os.sep):
        raise SystemExit(f"安全检查失败：拒绝操作 {real}")
    return real


def ignore(dir_path, names):
    out = []
    for n in names:
        if n in IGNORE_DIRS:
            out.append(n)
            continue
        low = n.lower()
        if any(fnmatch.fnmatch(low, p) for p in IGNORE_PATTERNS):
            out.append(n)
    return out


def check_version_gate() -> int:
    """发布门禁：版本号必须四处一致，且 CHANGELOG 里有当前版本的说明。

    在清理旧发布包**之前**执行 —— 没写版本说明就出不了包，
    也不会把上一版好不容易生成的 release/ 顺手删掉。
    """
    print("[门禁] 版本号与版本说明一致性")
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        import check_version
    except Exception as e:
        print(f"   跳过（无法导入 check_version: {type(e).__name__}: {e}）")
        return 0
    problems = check_version.verify(check_version.app_version())
    if problems:
        print(f"   FAIL  发现 {len(problems)} 个问题，拒绝出包：")
        for p in problems:
            print(f"     - {p}")
        print("        修好后重跑，或先补写 CHANGELOG.md")
        return 1
    print(f"   ok    版本 {check_version.app_version()} 一致，版本说明已就位")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只做安全校验，不生成")
    ap.add_argument("--skip-version-check", action="store_true",
                    help="跳过版本/说明文档门禁（仅用于调试，正常发布不要用）")
    args = ap.parse_args()

    rel = safe_target()
    if args.check:
        print(f"安全检查通过，目标目录: {rel}")
        return 0

    print("=" * 56)
    print("   生成发布包")
    print("=" * 56)
    if not args.skip_version_check:
        if check_version_gate():
            return 1
        print()
    print(f"   源目录: {ROOT}")
    print(f"   目标:   {rel}")
    print()

    if os.path.isdir(rel):
        print("[清理] 删除旧发布包...")
        shutil.rmtree(rel, ignore_errors=True)
    os.makedirs(rel, exist_ok=True)

    n_files = 0
    for tree in TREES:
        src = os.path.join(ROOT, tree)
        if not os.path.isdir(src):
            print(f"[跳过] {tree}/ 不存在")
            continue
        print(f"[复制] {tree}/")
        shutil.copytree(src, os.path.join(rel, tree), ignore=ignore,
                        dirs_exist_ok=True)
        n_files += sum(len(f) for _r, _d, f in os.walk(os.path.join(rel, tree)))

    print("[复制] 根目录文件")
    for name in ROOT_FILES:
        src = os.path.join(ROOT, name)
        if not os.path.exists(src):
            print(f"   跳过（缺失）: {name}")
            continue
        dst = os.path.join(rel, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
            n_files += 1

    # 自检：敏感内容绝不能进发布包
    print()
    print("[自检] 确认敏感内容未进入发布包")
    leaked = [p for p in FORBIDDEN if os.path.exists(os.path.join(rel, p))]
    for p in FORBIDDEN:
        mark = "泄露!" if p in leaked else "ok"
        print(f"   {mark:6s} {p}")

    # 自检：关键文件必须在（缺了会让人以为图标/启动入口没做进包里）
    print("[自检] 关键文件齐全性")
    missing = [p for p in REQUIRED if not os.path.exists(os.path.join(rel, p))]
    for p in REQUIRED:
        mark = "缺失!" if p in missing else "ok"
        print(f"   {mark:6s} {p}")

    size_mb = sum(os.path.getsize(os.path.join(r, f))
                  for r, _d, fs in os.walk(rel) for f in fs) / 1024 / 1024
    print()
    print("=" * 56)
    if leaked or missing:
        if leaked:
            print("   生成完成，但发现敏感内容泄露，请检查排除规则：")
            for p in leaked:
                print(f"     - {p}")
        if missing:
            print("   生成完成，但关键文件缺失，请检查排除规则：")
            for p in missing:
                print(f"     - {p}")
        print("=" * 56)
        return 1
    print(f"   发布包已生成: {rel}")
    print(f"   文件总数: {n_files} | 体积: {size_mb:.2f} MB")
    print("=" * 56)
    print("   上传方式：把 release 目录内容作为 GitHub 仓库内容")
    return 0


if __name__ == "__main__":
    sys.exit(main())
