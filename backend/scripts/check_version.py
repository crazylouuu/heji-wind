# -*- coding: utf-8 -*-
"""版本一致性门禁 —— 保证「改了版本号，就一定写了版本说明」。

检查项：
  1. backend/config.py 的 APP_VERSION（唯一真源；v1.3.0 起由 main.py 迁到此处，便于打包版统一维护）
  2. README.md 顶部徽章
  3. frontend/index.html 侧边栏页脚
  4. docs/用户手册.md 首行
  上面 4 处必须完全一致（不一致时页面/接口版本会打架）
  5. CHANGELOG.md 必须存在，且**最新一节**就是当前版本
     （写文档的人容易顺手把新版本追加到文件末尾，这里强制写在顶部）
  6. 该版本小节不能是空壳：必须有实质内容、必须点名至少一个代码文件
     （因为「改了哪些代码」是版本说明的核心，只写一句话不算说明）
  7. 全仓不能残留旧版本号（比如页脚还写着上个版本）

用法：
    backend\\venv\\Scripts\\python backend\\scripts\\check_version.py
    backend\\venv\\Scripts\\python backend\\scripts\\check_version.py -q   # 只输出结论
"""
import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)

CONFIG_PY = os.path.join(BACKEND, "config.py")
README = os.path.join(ROOT, "README.md")
INDEX_HTML = os.path.join(ROOT, "frontend", "index.html")
MANUAL = os.path.join(ROOT, "docs", "用户手册.md")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

# 版本说明小节的占位词：出现即视为没写
PLACEHOLDER = ("待补充", "TODO", "todo", "TBD", "略", "同上", "无")

VERSION_RE = re.compile(r"^\s*APP_VERSION\s*=\s*[\"']([^\"']+)[\"']", re.M)


def _read(path):
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None


def app_version():
    """从 backend/config.py 取当前版本号（唯一真源）。"""
    txt = _read(CONFIG_PY)
    if txt is None:
        return None
    m = VERSION_RE.search(txt)
    return m.group(1) if m else None


def _changelog_sections(txt):
    """把 CHANGELOG 拆成 [(版本号, 正文)]，按文件出现顺序。"""
    out = []
    parts = re.split(r"^##\s+", txt, flags=re.M)[1:]
    for p in parts:
        head, _, body = p.partition("\n")
        m = re.match(r"v?(\d+(?:\.\d+)*)", head.strip())
        if m:
            out.append((m.group(1), head.strip(), body))
    return out


def verify(version):
    """返回问题列表（空列表 = 全部通过）。"""
    problems = []

    if not version:
        problems.append("backend/config.py 里找不到 APP_VERSION")
        return problems

    # ---- 1. 四处版本号一致 ----
    readme = _read(README)
    if readme is None:
        problems.append("README.md 不存在")
    elif f"version-{version}-" not in readme:
        got = re.search(r"badge/version-([0-9.]+)-", readme)
        problems.append(
            f"README.md 徽章版本不一致：APP_VERSION={version}，"
            f"徽章里是 {got.group(1) if got else '找不到徽章'}")

    index = _read(INDEX_HTML)
    if index is None:
        problems.append("frontend/index.html 不存在")
    else:
        if f"v{version} " not in index and f"v{version}<" not in index:
            found = re.findall(r"v(\d+\.\d+(?:\.\d+)?)\s*[·<]", index)
            problems.append(
                f"frontend/index.html 页脚版本不一致：APP_VERSION={version}，"
                f"页面里是 {found or '找不到版本号'}")
        # 残留旧版本号（页脚/注释里写着别的版本）
        stale = sorted({v for v in re.findall(r"v(\d+\.\d+\.\d+)", index)
                        if v != version})
        if stale:
            problems.append(f"frontend/index.html 残留旧版本号：{stale}")

    manual = _read(MANUAL)
    if manual is None:
        problems.append("docs/用户手册.md 不存在")
    elif f"V{version}" not in manual:
        got = re.search(r"版本[：:]\s*V?([0-9.]+)", manual)
        problems.append(
            f"docs/用户手册.md 版本不一致：APP_VERSION={version}，"
            f"手册里是 {got.group(1) if got else '找不到版本号'}")

    # ---- 2. CHANGELOG 存在且有对应小节 ----
    log = _read(CHANGELOG)
    if log is None:
        problems.append("CHANGELOG.md 不存在 —— 每次版本变更都必须写版本说明")
        return problems

    sections = _changelog_sections(log)
    if not sections:
        problems.append("CHANGELOG.md 里没有任何 '## vX.Y.Z' 版本小节")
        return problems

    newest_ver, newest_head, newest_body = sections[0]
    if newest_ver != version:
        problems.append(
            f"CHANGELOG.md 最新一节是 v{newest_ver}，而当前版本是 v{version} —— "
            f"新版本的说明要写在文件顶部")

    found = next((s for s in sections if s[0] == version), None)
    if found is None:
        problems.append(f"CHANGELOG.md 缺少 v{version} 的说明小节")
        return problems

    _, head, body = found
    # ---- 3. 小节必须有实质内容 ----
    strip = re.sub(r"[#>*\-\s|`]", "", body)
    if len(strip) < 80:
        problems.append(f"CHANGELOG.md 的 v{version} 小节内容过少（不足 80 字），"
                        f"请写清实现的功能 / 代码改动 / 验证方式")
    hits = [w for w in PLACEHOLDER if w in body]
    if hits:
        # "无" 这类词可能正常出现在正文里，只提示不判死
        real = [w for w in hits if w != "无"]
        if real:
            problems.append(f"CHANGELOG.md 的 v{version} 小节疑似占位内容：{real}")
    # 必须点名代码文件
    files = re.findall(r"`([^`]+\.(?:py|js|html|css|bat|vbs|md|txt|json))`", body)
    if not files:
        problems.append(f"CHANGELOG.md 的 v{version} 小节没有点名任何代码文件"
                        f"（请写清改了哪些文件、增删了什么）")

    return problems


def main() -> int:
    quiet = "-q" in sys.argv
    version = app_version()
    print("=" * 62)
    print("   ChemELN 版本一致性检查")
    print("=" * 62)
    if quiet:
        problems = verify(version)
        for p in problems:
            print(f"     - {p}")
        print("=" * 62)
        return 1 if problems else 0

    print(f"    APP_VERSION = {version or '（读不到）'}（来自 backend/config.py）")
    problems = verify(version)
    print()
    if problems:
        print(f"    FAIL  发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"     - {p}")
        print("=" * 62)
        return 1
    print(f"    ok    4 处版本号一致，CHANGELOG.md 的 v{version} 说明已就位")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
