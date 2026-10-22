# -*- coding: utf-8 -*-
"""Generate demo data (compounds + sample experiments) for a fresh ChemELN install.

Usage:
    backend\\venv\\Scripts\\python backend\\scripts\\create_sample_data.py

Idempotent: skips if sample experiments already exist.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


SAMPLE_COMPOUNDS = [
    # (name, cas, smiles, mw, formula, category)
    ("乙醇", "64-17-5", "CCO", 46.07, "C2H6O", "solvent"),
    ("二氯甲烷", "75-09-2", "ClCCl", 84.93, "CH2Cl2", "solvent"),
    ("四氢呋喃", "109-99-9", "C1CCOC1", 72.11, "C4H8O", "solvent"),
    ("甲醇", "67-56-1", "CO", 32.04, "CH4O", "solvent"),
    ("乙酸乙酯", "141-78-6", "CCOC(=O)C", 88.11, "C4H8O2", "solvent"),
    ("苯甲醛", "100-52-7", "O=Cc1ccccc1", 106.12, "C7H6O", "reagent"),
    ("硼氢化钠", "16940-66-2", "[Na+].[BH4-]", 37.83, "NaBH4", "reagent"),
    ("4-溴苯胺", "106-40-1", "Nc1ccc(Br)cc1", 172.02, "C6H6BrN", "reagent"),
    ("苯硼酸", "98-80-6", "OB(O)c1ccccc1", 121.93, "C6H7BO2", "reagent"),
    ("碳酸钾", "584-08-7", "[K+].[K+].[O-]C(=O)[O-]", 138.21, "K2CO3", "reagent"),
    ("氢氧化钠", "1310-73-2", "[Na+].[OH-]", 40.00, "NaOH", "reagent"),
    ("N-(4-溴苄基)苯胺", "", "N(c1ccccc1)Cc1ccc(Br)cc1", 262.14, "C13H12BrN", "project"),
    ("4-甲氧基苯甲醛", "123-11-5", "COc1ccc(C=O)cc1", 136.15, "C8H8O2", "project"),
]


def _insert_compound(conn, name, cas, smiles, mw, formula, category):
    exists = conn.execute(
        "SELECT 1 FROM compounds WHERE name=? COLLATE NOCASE", (name,)).fetchone()
    if exists:
        return None
    cur = conn.execute(
        """INSERT INTO compounds (name, cas, smiles, inchikey, mw, formula, notes, category)
           VALUES (?, ?, ?, '', ?, ?, '示例数据', ?)""",
        (name, cas, smiles, mw, formula, category))
    return cur.lastrowid


def _insert_experiment(conn, title, project, status, exp_date, target, content,
                       fk_compound_id, reaction, reagents):
    cur = conn.execute(
        """INSERT INTO experiments
           (title, content, project, status, exp_date, target_compound,
            yield_pct, purity_pct, notes, fk_compound_id)
           VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, '示例数据', ?)""",
        (title, content, project, status, exp_date, target, fk_compound_id))
    eid = cur.lastrowid

    conn.execute(
        """INSERT INTO reactions
           (experiment_id, display_mode, reactant_smiles, product_smiles,
            conditions, arrow_label, image_path, notes)
           VALUES (?, 'scheme', ?, ?, ?, ?, '', '示例数据')""",
        (eid, json.dumps(reaction["reactants"], ensure_ascii=False),
         json.dumps(reaction["products"], ensure_ascii=False),
         reaction.get("conditions", ""), reaction.get("arrow_label", "")))

    for i, r in enumerate(reagents):
        rt = r.get("ratio_type", "equiv")
        rv = r.get("ratio_value")
        conn.execute(
            """INSERT INTO reagents
               (experiment_id, role, name, mw, ratio_type, ratio_value,
                equivalents, mass_g, moles_mmol, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, r["role"], r["name"], r.get("mw"), rt, rv,
             rv if rt == "equiv" else None, r.get("mass_g"),
             r.get("moles_mmol"), i))
    return eid


def main():
    database.init_db()
    conn = database.get_db()

    if conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE notes='示例数据'").fetchone()[0] > 0:
        print("示例数据已存在，跳过生成。")
        conn.close()
        return

    # --- 示例化合物 ---
    for c in SAMPLE_COMPOUNDS:
        _insert_compound(conn, *c)
    print("已插入示例化合物:", len(SAMPLE_COMPOUNDS))

    # --- 示例实验 1：还原胺化 ---
    e1_reactants = [
        {"name": "苯甲醛", "smiles": "O=Cc1ccccc1", "mw": 106.12, "formula": "C7H6O"},
        {"name": "4-溴苯胺", "smiles": "Nc1ccc(Br)cc1", "mw": 172.02, "formula": "C6H6BrN"},
    ]
    e1_products = [
        {"name": "N-(4-溴苄基)苯胺", "smiles": "N(c1ccccc1)Cc1ccc(Br)cc1",
         "mw": 262.14, "formula": "C13H12BrN"},
    ]
    e1_reagents = [
        {"role": "substrate", "name": "苯甲醛", "mw": 106.12,
         "ratio_type": "equiv", "ratio_value": 1.0, "mass_g": 5.0, "moles_mmol": 47.12},
        {"role": "reagent", "name": "4-溴苯胺", "mw": 172.02,
         "ratio_type": "equiv", "ratio_value": 1.0, "mass_g": 8.10, "moles_mmol": 47.12},
        {"role": "reagent", "name": "硼氢化钠", "mw": 37.83,
         "ratio_type": "equiv", "ratio_value": 1.5, "mass_g": 2.67, "moles_mmol": 70.68},
        {"role": "solvent", "name": "甲醇", "mw": 32.04,
         "ratio_type": "weight", "ratio_value": 5.0, "mass_g": 25.0},
    ]
    e1_content = (
        "<h2>实验目的</h2><p>演示示例：苯甲醛与对溴苯胺的还原胺化，验证 ChemELN 记录流程。</p>"
        "<h2>实验步骤</h2><ol>"
        "<li>将苯甲醛（5.0 g）与 4-溴苯胺（8.10 g）溶于甲醇（25 g）；</li>"
        "<li>冰浴下分批加入硼氢化钠（2.67 g），加毕室温搅拌 4 h；</li>"
        "<li>TLC 监测反应完全后，加水淬灭，乙酸乙酯萃取，浓缩得粗品。</li></ol>"
        "<h2>表征数据</h2><p>1H NMR: （示例占位）</p>"
    )
    e1_target = conn.execute(
        "SELECT id FROM compounds WHERE name='N-(4-溴苄基)苯胺'").fetchone()["id"]
    _insert_experiment(
        conn, "示例实验1：苯甲醛与对溴苯胺的还原胺化",
        "示例项目-还原胺化", "completed", "2026-08-20", "N-(4-溴苄基)苯胺",
        e1_content, e1_target,
        {"reactants": e1_reactants, "products": e1_products,
         "conditions": "甲醇, NaBH4, 0℃→rt, 4h", "arrow_label": "NaBH4"},
        e1_reagents)

    # --- 示例实验 2：Suzuki 偶联 ---
    e2_reactants = [
        {"name": "4-溴苯胺", "smiles": "Nc1ccc(Br)cc1", "mw": 172.02, "formula": "C6H6BrN"},
        {"name": "苯硼酸", "smiles": "OB(O)c1ccccc1", "mw": 121.93, "formula": "C6H7BO2"},
    ]
    e2_products = [
        {"name": "4-氨基联苯", "smiles": "Nc1ccc(-c2ccccc2)cc1", "mw": 169.22, "formula": "C12H11N"},
    ]
    e2_reagents = [
        {"role": "substrate", "name": "4-溴苯胺", "mw": 172.02,
         "ratio_type": "equiv", "ratio_value": 1.0, "mass_g": 2.0, "moles_mmol": 11.63},
        {"role": "reagent", "name": "苯硼酸", "mw": 121.93,
         "ratio_type": "equiv", "ratio_value": 1.2, "mass_g": 1.70, "moles_mmol": 13.96},
        {"role": "reagent", "name": "碳酸钾", "mw": 138.21,
         "ratio_type": "equiv", "ratio_value": 2.0, "mass_g": 3.21, "moles_mmol": 23.26},
        {"role": "catalyst", "name": "Pd(PPh3)4", "mw": 1155.56,
         "ratio_type": "weight", "ratio_value": 0.02, "mass_g": 0.04},
        {"role": "solvent", "name": "四氢呋喃", "mw": 72.11,
         "ratio_type": "weight", "ratio_value": 8.0, "mass_g": 16.0},
    ]
    e2_content = (
        "<h2>实验目的</h2><p>演示示例：Suzuki 偶联制备 4-氨基联苯。</p>"
        "<h2>实验步骤</h2><ol>"
        "<li>氮气保护下，将 4-溴苯胺（2.0 g）、苯硼酸（1.70 g）、碳酸钾（3.21 g）溶于 THF（16 g）；</li>"
        "<li>加入 Pd(PPh3)4（40 mg），90℃ 回流 12 h；</li>"
        "<li>冷却后过滤，浓缩，柱层析纯化得目标产物。</li></ol>"
        "<h2>表征数据</h2><p>1H NMR: （示例占位）</p>"
    )
    e2_target = None
    _insert_experiment(
        conn, "示例实验2：Suzuki 偶联制备 4-氨基联苯",
        "示例项目-Suzuki偶联", "ongoing", "2026-08-25", "4-氨基联苯",
        e2_content, e2_target,
        {"reactants": e2_reactants, "products": e2_products,
         "conditions": "K2CO3, Pd(PPh3)4, THF, 90℃, 12h", "arrow_label": "Pd(0), 90℃"},
        e2_reagents)

    conn.commit()
    conn.close()
    print("完成！示例数据已生成：")
    print("  - 示例化合物:", len(SAMPLE_COMPOUNDS), "条")
    print("  - 示例实验 2 条（含反应方程式与投料表）")
    print("打开 http://localhost:8765 即可查看。")


if __name__ == "__main__":
    main()
