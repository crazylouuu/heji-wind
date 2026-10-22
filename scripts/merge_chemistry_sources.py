#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性合并脚本：把两份历史数据合成 shared/chemistry-data.json。

只跑一次。之后改数据直接改 JSON，再用 build_chemistry_data.py 生成两侧。

合并策略
--------
1. **以 CAS 为唯一键**，取两份数据的并集。
2. **字段冲突**：
   - 工具箱的物性字段（bp/density/polarity/...）优先 —— 来自用户权威 Excel 表
   - 后端无物性字段，其独有 CAS 只贡献 name/aliases/formula/cas
   - formula 冲突时保留工具箱值（石油醚「混合烷烃」比「C6H14」更准确），
     并在 note 里记录后端原值，便于人工复核
3. **aliases 合并**：后端的 aliases 数组 + 工具箱的 en 字段（去重）
4. 物性字段缺失时置 null / 空串，不臆造
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS_SRC = ROOT / "src" / "data" / "solvents.ts"
PY_SRC = ROOT / "backend" / "utils" / "common_reagents.py"
OUT = ROOT / "shared" / "chemistry-data.json"

# 极性基础分类（前端筛选只用这 4 个值）。
# 原数据里有「弱极性(非质子)」「极性非质子(碱)」等带细化的写法，
# 合并时拆成 polarity（基础分类）+ polarity_note（括号里的细化说明），
# 这样前端下拉筛选只需 4 项，同时不丢失原有信息。
POLARITY_BASE = ("非极性", "弱极性", "极性非质子", "极性质子")


def split_polarity(raw: str):
    """把「弱极性(非质子)」拆成 ('弱极性', '非质子')。"""
    if not raw:
        return "", ""
    if "(" in raw and raw.endswith(")"):
        base, note = raw.split("(", 1)
        base, note = base.strip(), note[:-1].strip()
        if base in POLARITY_BASE:
            return base, note
        return raw.strip(), ""
    return raw.strip(), ""


# 前端 TS 的解析：按记录块切分，再逐块提取字段。
# 不用一条大正则 —— TS 里字段跨多行、risk 可能是空数组 []，
# 单条正则稍不留神就整块匹配失败（踩过这个坑）。
TS_BLOCK = re.compile(r'\{\s*name:\s*"[^"]*",\s*en:', re.S)


def _field(block: str, key: str, pattern: str = r'([^,}]*)'):
    m = re.search(rf'\b{key}:\s*{pattern}', block)
    return m.group(1).strip() if m else None


def parse_ts() -> list[dict]:
    text = TS_SRC.read_text(encoding="utf-8")
    # 只取 SOLVENTS 数组部分，避开 interface 声明
    arr = text[text.index("export const SOLVENTS"):]
    out = []
    # 按 "{ name: ... }," 切块
    starts = [m.start() for m in TS_BLOCK.finditer(arr)]
    for i, st in enumerate(starts):
        en = starts[i + 1] if i + 1 < len(starts) else len(arr)
        block = arr[st:en]
        # 块在下一个记录开始前结束；也可能含数组收尾 "];"
        block = block.split("];")[0]

        def num(key):
            v = _field(block, key, r'(-?[\d.]+|null)')
            if v in (None, "", "null"):
                return None
            return float(v)

        risk_raw = _field(block, "risk", r'\[([^\]]*)\]') or ""
        risk = [x.strip().strip('"') for x in risk_raw.split(",") if x.strip()]
        miscible = (_field(block, "miscible", r'(true|false)') or "false") == "true"

        out.append({
            "name": (_field(block, "name", r'"([^"]*)"') or ""),
            "en": (_field(block, "en", r'"([^"]*)"') or ""),
            "formula": (_field(block, "formula", r'"([^"]*)"') or ""),
            "cas": (_field(block, "cas", r'"([0-9-]+)"') or ""),
            "bp": num("bp"),
            "density": num("density"),
            "polarity": (_field(block, "polarity", r'"([^"]*)"') or ""),
            "dielectric": num("dielectric"),
            "miscible": miscible,
            "solubility": (_field(block, "solubility", r'"([^"]*)"') or ""),
            "flash": num("flash"),
            "risk": risk,
            "hazard": (_field(block, "hazard", r'"([^"]*)"') or ""),
            "use": (_field(block, "use", r'"([^"]*)"') or ""),
            "desiccant": (_field(block, "desiccant", r'"([^"]*)"') or ""),
        })
    return out


def parse_py() -> list[dict]:
    """从 common_reagents.py 提取 (name, aliases, formula, cas)。"""
    text = PY_SRC.read_text(encoding="utf-8")
    out = []
    # 用 ast 解析更稳，但文件可能 import 失败；这里用 ast 只取字面量
    import ast
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "COMMON_REAGENTS" for t in node.targets):
            for elt in node.value.elts:
                if not isinstance(elt, ast.Tuple) or len(elt.elts) != 4:
                    continue
                try:
                    name = ast.literal_eval(elt.elts[0])
                    aliases = ast.literal_eval(elt.elts[1])
                    formula = ast.literal_eval(elt.elts[2])
                    cas = ast.literal_eval(elt.elts[3])
                except Exception:
                    continue
                out.append({
                    "name": name, "aliases": aliases,
                    "formula": formula, "cas": cas,
                })
            break
    return out


def main() -> int:
    ts = parse_ts()
    py = parse_py()
    print(f"解析 solvents.ts: {len(ts)} 条")
    print(f"解析 common_reagents.py: {len(py)} 条")

    by_cas: dict[str, dict] = {}
    conflicts = []

    # 1. 先放后端数据（字段少，作为基底）
    for r in py:
        if not r["cas"]:
            continue
        by_cas[r["cas"]] = {
            "name": r["name"],
            "en": "",
            "formula": r["formula"],
            "cas": r["cas"],
            "bp": None, "density": None, "polarity": "", "polarity_note": "",
            "dielectric": None,
            "miscible": False, "solubility": "", "flash": None,
            "risk": [], "hazard": "", "use": "", "desiccant": "",
            "aliases": list(r["aliases"]),
        }

    # 2. 用工具箱数据覆盖/合并
    for r in ts:
        cas = r["cas"]
        if cas in by_cas:
            base = by_cas[cas]
            # formula 冲突：保留工具箱值，记录后端原值
            if base["formula"].replace(" ", "") != r["formula"].replace(" ", ""):
                conflicts.append((cas, base["name"], base["formula"], r["formula"]))
                base["formula"] = r["formula"]
            # aliases 合并（后端 aliases + 工具箱 en）
            al = set(base["aliases"])
            if r["en"]:
                al.add(r["en"])
            base["aliases"] = sorted(al)
            # 物性字段用工具箱的（权威 Excel 来源）
            for f in ("bp", "density", "dielectric", "miscible",
                      "solubility", "flash", "risk", "hazard", "use", "desiccant"):
                base[f] = r[f]
            # polarity 拆成基础分类 + 细化说明
            pol, pol_note = split_polarity(r["polarity"])
            base["polarity"] = pol
            base["polarity_note"] = pol_note
            # name/en 用工具箱的（中文名更规范）
            if r["name"]:
                base["name"] = r["name"]
            if r["en"]:
                base["en"] = r["en"]
        else:
            # 工具箱独有 CAS
            al = set()
            if r["en"]:
                al.add(r["en"])
            pol, pol_note = split_polarity(r["polarity"])
            by_cas[cas] = {
                **{k: r[k] for k in ("name", "en", "formula", "cas", "bp", "density",
                                     "dielectric", "miscible", "solubility",
                                     "flash", "risk", "hazard", "use", "desiccant")},
                "polarity": pol,
                "polarity_note": pol_note,
                "aliases": sorted(al),
            }

    chems = sorted(by_cas.values(), key=lambda x: (x["name"], x["cas"]))

    # 3. 统计
    ts_cas = {r["cas"] for r in ts}
    py_cas = {r["cas"] for r in py if r["cas"]}
    both = ts_cas & py_cas
    only_ts = ts_cas - py_cas
    only_py = py_cas - ts_cas
    print()
    print(f"两边都有: {len(both)}   仅工具箱: {len(only_ts)}   仅后端: {len(only_py)}")
    print(f"合并后唯一 CAS: {len(chems)}")
    print(f"有完整物性字段的（源自工具箱）: {sum(1 for c in chems if c['bp'] is not None)}")

    if conflicts:
        print()
        print("formula 冲突（保留工具箱值）:")
        for cas, n, old, new in conflicts:
            print(f"  {cas} {n}: {old!r} -> {new!r}")

    out = {
        "meta": {
            "description": "ChemLab 常用溶剂/试剂物性与标识数据（单一真源）",
            "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sources": [
                "工具箱 src/data/solvents.ts（98 种，源自用户《常用溶剂物性表.xlsx》权威表，2026-09-24）",
                "chemELN backend/utils/common_reagents.py（175 种，name+aliases+formula+cas）",
            ],
            "merge_policy": "以 CAS 为唯一键取并集；物性字段以工具箱（权威 Excel）为准；"
                            "aliases 合并两侧；formula 冲突保留工具箱值",
            "count": len(chems),
            "note": "实际使用请以试剂瓶标签、最新 SDS 与最新版名录为准；本数据仅作查询参考。",
        },
        "chemicals": chems,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"已写出 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
