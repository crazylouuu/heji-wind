# -*- coding: utf-8 -*-
"""发布前脚本体检 — 在交付/上传前自动检查所有脚本的坑。

检查项：
  1. .bat 能否按 GBK 解码（UTF-8 存的中文会被 cmd 解错、中文路径静默失败）
  2. .bat / .vbs 是否为 CRLF（LF-only 会让 goto/标签解析异常）
  3. 脚本内 %~dp0 / baseDir 引用的路径是否真实存在（防路径被转义吞掉）
  4. backend 源码中含 print/log 的行是否出现 GBK 编不出的字符
     （服务以隐藏窗口 + 重定向启动时会 UnicodeEncodeError 秒退）

用法：
    backend\\venv\\Scripts\\python backend\\scripts\\check_scripts.py
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

# 允许 GBK 编不出的字符白名单（无）
FAILS = []


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("gbk", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc), enc, raw
        except UnicodeDecodeError:
            continue
    return None, None, raw


def check_scripts():
    print("[1] 脚本编码 / 换行 / 路径引用")
    names = sorted(f for f in os.listdir(ROOT)
                   if f.lower().endswith((".bat", ".vbs")))
    for name in names:
        path = os.path.join(ROOT, name)
        txt, enc, raw = read_text(path)
        issues = []
        if txt is None:
            issues.append("无法按 GBK/UTF-8 解码")
            txt = ""
        elif enc != "gbk" and name.lower().endswith(".bat"):
            issues.append(f"编码为 {enc}，应为 GBK（中文会被 cmd 解错）")

        if name.lower().endswith((".bat", ".vbs")):
            if raw.count(b"\n") != raw.count(b"\r\n"):
                issues.append("存在裸 LF，应为纯 CRLF")

        # 控制字符污染（例如 \v \f 被吃掉）
        ctrl = [c for c in txt if ord(c) < 32 and c not in "\r\n\t"]
        if ctrl:
            issues.append(f"含 {len(ctrl)} 个异常控制字符（转义被吞）")

        # 路径引用有效性
        refs = re.findall(r"%~dp0([^\"\s)]*)", txt)
        refs += re.findall(r'baseDir\s*&\s*"\\([^"]*)"', txt)
        for r in refs:
            r = r.strip().strip('"').replace("\\", os.sep)
            if not r:
                continue
            if not os.path.exists(os.path.join(ROOT, r)):
                issues.append(f"引用不存在的路径: {r}")

        mark = "FAIL" if issues else "ok  "
        print(f"    {mark}  {name:26s} enc={enc or '?':8s} refs={len(refs)}")
        for it in issues:
            print(f"            - {it}")
            FAILS.append(f"{name}: {it}")
    if not names:
        print("    （未找到脚本）")


def check_python_output():
    print()
    print("[2] Python 源码输出字符（GBK 安全性）")
    bad_total = 0
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in
                   ("venv", "data", "__pycache__", "node_modules")]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, ROOT)
            hits = []
            try:
                lines = open(path, encoding="utf-8", errors="replace").readlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                if not re.search(r"\b(print|_log|logger\.|logging\.)\s*\(", line):
                    continue
                for ch in line:
                    try:
                        ch.encode("gbk")
                    except UnicodeEncodeError:
                        hits.append((i, ch, line.strip()[:70]))
                        break
            if hits:
                bad_total += len(hits)
                print(f"    FAIL  {rel}")
                for i, ch, ln in hits[:5]:
                    print(f"            line {i}: U+{ord(ch):04X} '{ch}' | {ln}")
                FAILS.append(f"{rel}: {len(hits)} 处不可 GBK 编码的输出")
    if bad_total == 0:
        print("    ok    全部服务端输出均可按 GBK 编码")


def check_desktop_entry():
    """桌面启动入口在项目目录之外，最容易被手工改坏/被旧副本覆盖。

    真实事故：桌面旧副本是 UTF-8 + LF-only 的，cmd 按 GBK 解码后中文乱码，
    乱码字节破坏引号配对，双击 0.1 秒就 exit=1 —— 用户看到「窗口一闪，
    页面打不开」，而项目内的脚本完全是好的。故纳入发布前体检。
    """
    print()
    print("[3] 桌面启动入口（项目外，易被旧副本覆盖腐化）")
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        import setup_env
    except Exception as e:
        print(f"    跳过（无法导入 setup_env: {type(e).__name__}: {e}）")
        return
    target = os.path.join(setup_env.desktop_dir(), setup_env.DESKTOP_BAT_NAME)
    if not os.path.exists(target):
        print(f"    ok     {setup_env.DESKTOP_BAT_NAME} 不在桌面（可选，install.bat 会创建）")
        return
    problems = setup_env.check_desktop_launcher()
    if problems:
        print(f"    FAIL   {setup_env.DESKTOP_BAT_NAME}")
        for p in problems:
            print(f"            - {p}")
            FAILS.append(f"桌面入口: {p}")
    else:
        print(f"    ok     {setup_env.DESKTOP_BAT_NAME} 正常（纯 ASCII / CRLF / 无 BOM）")


def main() -> int:
    print("=" * 62)
    print("   ChemELN 发布前脚本体检")
    print("=" * 62)
    check_scripts()
    check_python_output()
    check_desktop_entry()
    print()
    print("=" * 62)
    if FAILS:
        print(f"   发现 {len(FAILS)} 个问题：")
        for f in FAILS:
            print(f"     - {f}")
        print("=" * 62)
        return 1
    print("   全部通过，可以发布")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
