# -*- coding: utf-8 -*-
"""ChemELN 冒烟测试 — 进程内用 TestClient 拉起服务，逐个验证关键路由。

用途：不占用 8765 端口、不需要常驻进程，即可确认服务端是否可正常启动与响应。
用法：
    backend\\venv\\Scripts\\python backend\\scripts\\smoke_test.py
"""
import os
import sys

try:
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

FAILS = []


def check(name, method, path, expect=200, **kw):
    with TestClient(main.app) as c:
        r = getattr(c, method)(path, **kw)
    ok = r.status_code == expect
    body = r.text[:120].replace("\n", " ")
    print(("  OK  " if ok else "  FAIL") + f" {method.upper():4s} {path} -> {r.status_code}")
    if not ok:
        FAILS.append((name, path, r.status_code, body))
    return r


def main_run():
    print("ChemELN 冒烟测试")
    print("-" * 52)

    r = check("首页", "get", "/")
    if r.status_code == 200 and "ChemELN" in r.text:
        print("       index.html 含标题，正常")
    else:
        FAILS.append(("首页内容", "/", r.status_code, "标题缺失"))

    check("健康检查", "get", "/api/health")
    check("实验列表", "get", "/api/experiments")
    check("实验筛选-步骤", "get", "/api/experiments?step=1")
    check("化合物-项目库", "get", "/api/compounds?category=project")
    check("化合物-溶剂库", "get", "/api/compounds?category=solvent")
    check("化合物-试剂库", "get", "/api/compounds?category=reagent")
    check("模板列表", "get", "/api/templates")
    check("搜索统计", "get", "/api/search/stats")

    print("-" * 52)
    print("自动备份接口")
    s = check("备份设置-读", "get", "/api/data/backup/settings")
    if s.status_code == 200:
        print(f"       现有配置: {s.json()}")
        check("备份设置-写", "put", "/api/data/backup/settings",
              json={"enabled": True, "interval_hours": 24, "keep": 7})
    b = check("备份-立即执行", "post", "/api/data/backup/run")
    if b.status_code == 200:
        d = b.json()
        print(f"       产出: {d.get('name')} / {d.get('size', 0)/1024:.1f} KB")
    check("备份列表", "get", "/api/data/backup/list")

    print("-" * 52)
    if FAILS:
        print(f"失败 {len(FAILS)} 项：")
        for f in FAILS:
            print(f"  - {f[0]} {f[1]} -> {f[2]} | {f[3]}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main_run())
