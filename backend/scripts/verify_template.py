#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在数据库临时副本上验证「模板 → 新建实验」的端到端链路。

不触碰真实数据库：先把 chemeln.db 复制到临时目录，改写 database.DB_PATH，
再直接调用路由函数。验证完即删除临时库。
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

import database  # noqa: E402

REAL_DB = database.DB_PATH
TEMPLATE_ID = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
TEMPLATE_NAME = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isdigit() else None

tmpdir = tempfile.mkdtemp(prefix="chemeln_verify_")
tmp_db = os.path.join(tmpdir, "chemeln_test.db")
shutil.copy2(REAL_DB, tmp_db)
database.DB_PATH = tmp_db

from routers import experiments as EX  # noqa: E402

fails = []


def check(label, cond, detail=""):
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", label, ("  " + detail) if detail else ""))
    if not cond:
        fails.append(label)


print("=" * 70)
print("  模板 → 新建实验 端到端验证（临时库副本，真实数据未改动）")
print("=" * 70)
print("  临时库: %s" % tmp_db)
print()

# --- 读取模板 ---
conn = sqlite3.connect(tmp_db)
conn.row_factory = sqlite3.Row
if TEMPLATE_NAME:
    tpl = conn.execute("SELECT * FROM templates WHERE name=?", (TEMPLATE_NAME,)).fetchone()
    if tpl:
        TEMPLATE_ID = tpl["id"]
else:
    tpl = conn.execute("SELECT * FROM templates WHERE id=?", (TEMPLATE_ID,)).fetchone()
if not tpl:
    print("模板不存在（id=%s name=%s）" % (TEMPLATE_ID, TEMPLATE_NAME))
    sys.exit(1)
print("模板: %s (type=%s)" % (tpl["name"], tpl["type"]))
print("  正文 %d 字符 | 投料模板 %d 行 | 反应模板 %s"
      % (len(tpl["content"] or ""),
         len(json.loads(tpl["reagent_template"] or "[]")),
         "有" if (tpl["reaction_template"] or "").strip() not in ("", "{}") else "无"))
conn.close()
print()

# --- 由模板新建实验 ---
res = EX.create_experiment(EX.ExperimentCreate(
    title="【验证】项目1-Step1 硝化", project="验证项目", status="draft",
    template_id=TEMPLATE_ID, step_no=1))
eid = res["id"]
print("已创建实验 id=%s" % eid)
print()

conn = sqlite3.connect(tmp_db)
conn.row_factory = sqlite3.Row
exp = conn.execute("SELECT * FROM experiments WHERE id=?", (eid,)).fetchone()
reagents = conn.execute(
    "SELECT * FROM reagents WHERE experiment_id=? ORDER BY sort_order", (eid,)).fetchall()
rxn = conn.execute("SELECT * FROM reactions WHERE experiment_id=?", (eid,)).fetchone()

print("--- 1. 正文内容继承 ---")
content = exp["content"] or ""
for sec in ["反应方程式", "投料表", "工艺条件", "操作步骤", "后处理与纯化", "关键控制点与安全"]:
    check("正文含章节「%s」" % sec, sec in content)
check("正文含安全条款（混酸放热）", "混酸放热极烈" in content)
print()

print("--- 2. 投料表继承 ---")
expect = [
    ("项目1-SM", "substrate", "equiv", 140.569, None, None),
    ("浓硝酸", "reagent", "equiv", 63.012, 1.41, 68.0),
    ("浓硫酸", "solvent", "weight", 98.079, 1.84, 98.0),
    ("水", "solvent", "weight", 18.015, 1.0, 100.0),
    ("DCM", "solvent", "weight", 84.933, 1.33, None),
    ("正庚烷", "solvent", "weight", 100.205, 0.684, None),
]
check("投料行数 = %d" % len(expect), len(reagents) == len(expect), "实际 %d" % len(reagents))
for row, (nm, role, rt, mw, dens, pur) in zip(reagents, expect):
    ok = (row["name"] == nm and row["role"] == role
          and row["ratio_type"] == rt and abs((row["mw"] or 0) - mw) < 0.01)
    detail = "期望 %s/%s/%s/%s" % (nm, role, rt, mw) if not ok else ""
    check("%-10s 角色=%-9s 投料比=%-6s MW=%s" % (row["name"], row["role"], row["ratio_type"], row["mw"]),
          ok, detail)
    if dens is not None:
        check("  └ 密度 = %s" % dens, row["density"] is not None and abs(row["density"] - dens) < 1e-6,
              "实际 %s" % row["density"])
    if pur is not None:
        check("  └ 商品浓度 = %s%%" % pur,
              row["purity_pct"] is not None and abs(row["purity_pct"] - pur) < 1e-6,
              "实际 %s" % row["purity_pct"])
print()

print("--- 3. 反应式继承 ---")
if rxn:
    rea = json.loads(rxn["reactant_smiles"] or "[]")
    pro = json.loads(rxn["product_smiles"] or "[]")
    check("存在反应记录", True)
    check("反应物 1 个: %s" % (rea[0]["name"] if rea else "-"), len(rea) == 1 and rea[0]["name"] == "项目1-SM",
          rea[0]["smiles"] if rea else "")
    check("产物 1 个: %s" % (pro[0]["name"] if pro else "-"), len(pro) == 1 and pro[0]["name"] == "项目1-A1",
          pro[0]["smiles"] if pro else "")
    check("display_mode = scheme", rxn["display_mode"] == "scheme", rxn["display_mode"])
    check("反应条件 = HNO3 / H2SO4", rxn["conditions"] == "HNO3 / H2SO4", rxn["conditions"] or "(空)")
    check("箭头标注 = 0~5℃", rxn["arrow_label"] == "0~5℃", rxn["arrow_label"] or "(空)")
else:
    check("存在反应记录", False)
print()

print("--- 4. 投料表联动计算（模拟前端 localCalculate）---")
sub = [r for r in reagents if r["role"] == "substrate"][0]
sub_mass = 5.0                      # 假设投 5 g 原料
sub_moles = sub_mass * 1000 / sub["mw"]   # mmol
print("  基准: 项目1-SM %.1f g / MW %.3f → %.2f mmol" % (sub_mass, sub["mw"], sub_moles))
sample = [("浓硝酸", 1.2, "equiv"), ("浓硫酸", 5.0, "weight")]
for name, val, kind in sample:
    row = [r for r in reagents if r["name"] == name][0]
    if kind == "equiv":
        moles = sub_moles * val
        purity = (row["purity_pct"] or 100) / 100.0
        mass = moles * row["mw"] / 1000 / purity
        vol = mass / row["density"] if row["density"] else None
        print("  %-6s %s eq → %.2f mmol → %.2f g%s%s" % (
            name, val, moles, mass,
            ("（按 %g%% 商品浓度折算）" % (purity * 100)) if purity < 1 else "",
            (" / %.2f mL" % vol) if vol else ""))
    else:
        print("  %-6s %s wt → %.2f g (%g%% 规格)" % (
            name, val, val * sub_mass, row["purity_pct"] or 100))
check("联动计算链路可用（原料 MW 与摩尔数可算）", sub_moles > 0 and sub["mw"] > 0)
check("浓硝酸带商品浓度，用量按 100% 折算", [r for r in reagents if r["name"] == "浓硝酸"][0]["purity_pct"] == 68.0)
check("浓硝酸带密度，可算体积", [r for r in reagents if r["name"] == "浓硝酸"][0]["density"] == 1.41)
print()

conn.close()
shutil.rmtree(tmpdir, ignore_errors=True)
print("=" * 70)
if fails:
    print("结果: %d 项未通过 -> %s" % (len(fails), "; ".join(fails)))
else:
    print("结果: 全部通过（临时库已删除，真实数据未改动）")
print("=" * 70)
sys.exit(1 if fails else 0)
