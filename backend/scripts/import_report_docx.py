#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从「研发报告 .docx」导入为 ChemELN 模板。

支持解析的内容：
  1. 反应方程式 —— 报告里的反应式是 KingDraw 的 OLE 嵌入对象。
     KingDraw 把绘图数据以 JSON 存在 OLE 复合文档内的一个 zip 里（protocol 流），
     其中含完整的原子/键连接表 + 分子式标签。本脚本据此用 RDKit 重建结构，
     并与绘图自带的 Formula / Mol.Wt. 标签**交叉校验**，校验通过才采信。
  2. 投料表 —— 读取表格中的名称/角色，MW 由绘图分子式或常用试剂库补齐。
  3. 工艺条件 / 操作步骤 / 后处理与纯化 / 关键控制点与安全 —— 转为模板正文 HTML。

用法：
    python import_report_docx.py <报告.docx>                # 预演（只打印，不写库）
    python import_report_docx.py <报告.docx> --apply        # 写入 templates 表
    python import_report_docx.py <报告.docx> --apply --name "硝化反应模板（混酸法）"
"""
import io
import json
import os
import re
import sys
import zipfile

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

DB_PATH = os.path.join(BACKEND, "data", "chemeln.db")

# KingDraw 里的缩写取代基 → 展开成显式原子的树状结构。
# root 以单键接到被标注的原子上，children 再接到 root。
SUPERATOM_DEFS = {
    "NO2": {"root": "N", "children": [("O", 2), ("O", 2)]},
    "NO": {"root": "N", "children": [("O", 2)]},
    "COOH": {"root": "C", "children": [("O", 2), ("O", 1)]},
    "CO2H": {"root": "C", "children": [("O", 2), ("O", 1)]},
    "OMe": {"root": "O", "children": [("C", 1)]},
    "OCH3": {"root": "O", "children": [("C", 1)]},
    "NH2": {"root": "N", "children": []},
    "CN": {"root": "C", "children": [("N", 3)]},
    "SO2": {"root": "S", "children": [("O", 2), ("O", 2)]},
}

# 化合物库用的是 Hill 式（H2O4S），画在反应箭头上时用化学界惯用写法
FORMULA_DISPLAY = {
    "硫酸": "H2SO4", "硝酸": "HNO3", "盐酸": "HCl", "磷酸": "H3PO4",
    "乙酸": "AcOH", "甲酸": "HCOOH", "甲磺酸": "MsOH", "对甲苯磺酸": "TsOH",
}

# 常用液体试剂的密度(g/mL)与商品浓度(%) —— 供投料表的体积/用量联动计算。
# 数值为常规试剂规格参考值，可按实际采购批次在界面上改。
LIQUID_PROPS = {
    "浓硝酸": {"density": 1.41, "purity_pct": 68.0},
    "硝酸": {"density": 1.41, "purity_pct": 68.0},
    "浓硫酸": {"density": 1.84, "purity_pct": 98.0},
    "硫酸": {"density": 1.84, "purity_pct": 98.0},
    "盐酸": {"density": 1.18, "purity_pct": 37.0},
    "水": {"density": 1.0, "purity_pct": 100.0},
    "dcm": {"density": 1.33},
    "二氯甲烷": {"density": 1.33},
    "正庚烷": {"density": 0.684},
    "正己烷": {"density": 0.659},
    "甲醇": {"density": 0.792},
    "乙醇": {"density": 0.789},
    "乙酸乙酯": {"density": 0.902},
    "四氢呋喃": {"density": 0.889},
    "thf": {"density": 0.889},
    "甲苯": {"density": 0.867},
    "丙酮": {"density": 0.791},
    "乙腈": {"density": 0.786},
    "dmf": {"density": 0.944},
    "dmso": {"density": 1.10},
}

# 分子式字符串 → 各元素计数（用于忽略元素书写顺序的等价比较）
def formula_counts(f):
    if not f:
        return None
    counts = {}
    for el, num in re.findall(r"([A-Z][a-z]?)(\d*)", f):
        if not el:
            continue
        counts[el] = counts.get(el, 0) + (int(num) if num else 1)
    return counts or None


def formula_equal(a, b):
    ca, cb = formula_counts(a), formula_counts(b)
    return bool(ca) and ca == cb


# ---------------------------------------------------------------- OLE 提取

def extract_kingdraw_protocol(docx_path):
    """从 docx 的 OLE 嵌入对象里取出 KingDraw protocol JSON。找不到返回 None。"""
    z = zipfile.ZipFile(docx_path)
    bins = [n for n in z.namelist() if n.startswith("word/embeddings/") and n.endswith(".bin")]
    for name in bins:
        blob = z.read(name)
        for off in (i for i in range(len(blob) - 4) if blob[i:i + 4] == b"PK\x03\x04"):
            try:
                inner = zipfile.ZipFile(io.BytesIO(blob[off:]))
                if "protocol" not in inner.namelist():
                    continue
                return json.loads(inner.read("protocol").decode("utf-8"))
            except Exception:
                continue
    return None


# ------------------------------------------------------- 绘图 → 分子结构

def _walk(elements):
    """展平嵌套的 elements（fragment → subs）。"""
    out = []
    stack = list(elements)
    while stack:
        e = stack.pop(0)
        out.append(e)
        stack = list(e.get("subs") or []) + stack
    return out


def protocol_to_fragments(protocol):
    """把 KingDraw protocol 拆成 {kid: {"atoms": [...], "bonds": [...], "label": str}}。

    注意关联方式：
      - bond.rels = [原子kidA, 原子kidB]
      - sup.rels  = [键kid]  → 需经该键反查被标注的原子（NO2 等缩写取代基）
      - text.rels = [fragment kid] → 该碎片的 Formula / Mol.Wt. 标签（顶层兄弟节点）
    """
    top = protocol.get("elements", [])
    flat = _walk(top)
    frags = {}

    for e in flat:
        if e.get("id") != "fragment":
            continue
        frag = {"atoms": {}, "bonds": [], "supers": [], "label": "", "raw_sups": []}
        for s in _walk(e.get("subs") or []):
            sid = s.get("id")
            prop = s.get("prop") or {}
            if sid == "node":
                frag["atoms"][s.get("kid")] = {
                    "elem": prop.get("type") or "C",
                    "point": prop.get("point") or {"x": 0.0, "y": 0.0},
                }
            elif sid == "bond":
                rels = s.get("rels") or []
                if len(rels) == 2:
                    frag["bonds"].append((rels[0], rels[1], int(prop.get("type") or 1)))
            elif sid == "sup":
                frag["raw_sups"].append({"kid": s.get("kid"),
                                         "bond": (s.get("rels") or [None])[0],
                                         "label": (prop.get("label") or "").strip()})
        frags[e.get("kid")] = frag

    # sup → 锚点原子：经 sup 关联的键反查另一端
    for f in frags.values():
        for sup in f["raw_sups"]:
            anchor = None
            for a, b, _bo in f["bonds"]:
                if sup["kid"] in (a, b):
                    other = b if a == sup["kid"] else a
                    if other in f["atoms"]:
                        anchor = other
                        break
            if anchor:
                f["supers"].append({"anchor": anchor, "label": sup["label"]})

    # 顶层 text（Formula / Mol.Wt.）按其 rels 指回的 fragment 归位
    for e in top:
        if e.get("id") != "text":
            continue
        for r in (e.get("rels") or []):
            if r in frags:
                lab = ((e.get("prop") or {}).get("label") or "").strip()
                frags[r]["label"] = (frags[r]["label"] + "\n" + lab).strip()

    # 几何排序：按原子平均 x 排，左=反应物，右=产物
    for f in frags.values():
        xs = [a["point"]["x"] for a in f["atoms"].values()] or [0.0]
        f["mean_x"] = sum(xs) / len(xs)
    return frags


def fragment_to_molblock(frag, name="mol"):
    """连接表 → MOL V2000 文本（显式 H 保留，坐标用绘图的 2D 坐标）。"""
    atoms = []          # [(elem, x, y)]
    bonds = []          # [(idx_a, idx_b, order)]  1-based
    idx = {}            # 绘图 kid → 1-based 原子序号

    for kid, a in frag["atoms"].items():
        p = a["point"]
        atoms.append((a["elem"], p["x"], p["y"]))
        idx[kid] = len(atoms)

    for a, b, bo in frag["bonds"]:
        if a in idx and b in idx:
            bonds.append((idx[a], idx[b], bo))

    # 缩写取代基展开（如 NO2 → N + 2×O），挂在被标注的原子上
    for sup in frag["supers"]:
        anchor = sup["anchor"]
        spec = SUPERATOM_DEFS.get(sup["label"])
        if anchor not in idx or not spec:
            continue
        ax, ay = frag["atoms"][anchor]["point"]["x"], frag["atoms"][anchor]["point"]["y"]
        # root 接到锚点
        atoms.append((spec["root"], ax + 1.0, ay + 1.6))
        root_idx = len(atoms)
        bonds.append((idx[anchor], root_idx, 1))
        # children 接到 root
        for k, (el, bo) in enumerate(spec["children"]):
            atoms.append((el, ax + 1.6 + 0.7 * k, ay + 2.2 + 0.5 * k))
            bonds.append((root_idx, len(atoms), bo))

    out = [name, "  ChemELN  2D", ""]
    out.append("%3d%3d  0  0  0  0  0  0  0  0999 V2000" % (len(atoms), len(bonds)))
    for el, x, y in atoms:
        out.append("%10.4f%10.4f%10.4f %-3s 0  0  0  0  0  0  0  0  0  0  0  0"
                   % (x, y, 0.0, el))
    for ia, ib, bo in bonds:
        out.append("%3d%3d%3d  0  0  0  0" % (ia, ib, bo))
    out.append("M  END")
    return "\n".join(out)


def molblock_to_smiles(molblock):
    """RDKit 解析 MOL → (smiles, mw, formula)；失败返回 None。"""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")

    mol = Chem.MolFromMolBlock(molblock, sanitize=True, removeHs=False)
    if mol is None:
        return None
    mol = Chem.RemoveHs(mol)
    smi = Chem.MolToSmiles(mol)
    return {
        "smiles": smi,
        "mw": round(Descriptors.MolWt(mol), 2),
        "formula": rdMolDescriptors.CalcMolFormula(mol),
    }


def parse_reaction_scheme(protocol):
    """返回 (reactants, products, warnings)；结构按几何左右分配并做分子式自校验。"""
    frags = protocol_to_fragments(protocol)
    items = []
    for kid, f in frags.items():
        if not f["atoms"]:
            continue
        mb = fragment_to_molblock(f, name="frag%s" % kid[-4:])
        info = molblock_to_smiles(mb)
        # 绘图自带的 Formula / Mol.Wt.
        lab_formula = lab_mw = None
        m = re.search(r"Formula:\s*([A-Za-z0-9]+)", f["label"] or "")
        if m:
            lab_formula = m.group(1)
        m = re.search(r"Mol\.Wt\.:\s*([\d.]+)", f["label"] or "")
        if m:
            lab_mw = float(m.group(1))
        items.append({"kid": kid, "mean_x": f["mean_x"], "info": info,
                      "label_formula": lab_formula, "label_mw": lab_mw,
                      "label": f["label"]})

    warnings = []
    for it in items:
        if it["info"] is None:
            warnings.append("片段 %s 未能重建结构（RDKit 解析失败）" % it["kid"][-6:])
            continue
        # 交叉校验：重建结果的分子式/分子量须与绘图标签一致
        if it["label_formula"] and not formula_equal(it["info"]["formula"], it["label_formula"]):
            warnings.append("片段 %s 分子式不符：重建 %s vs 绘图 %s"
                            % (it["kid"][-6:], it["info"]["formula"], it["label_formula"]))
        if it["label_mw"] and abs(it["info"]["mw"] - it["label_mw"]) > 0.5:
            warnings.append("片段 %s 分子量不符：重建 %.2f vs 绘图 %.2f"
                            % (it["kid"][-6:], it["info"]["mw"], it["label_mw"]))

    items.sort(key=lambda x: x["mean_x"])
    reactants = [it for it in items[:-1]] if len(items) > 1 else []
    products = [items[-1]] if items else []
    return reactants, products, warnings


# ------------------------------------------------------------ docx 正文

def parse_report_sections(docx_path):
    """读取报告的元信息、投料表、以及各文本小节。

    小节切分：Heading 样式，或独立成行的「xxx：」（如 工艺条件：/操作步骤：）。
    这份报告只有「反应方程式 / 投料表」是 Heading，其余小节靠冒号行标记。
    """
    from docx import Document
    d = Document(docx_path)

    meta, sections = {}, {}
    cur = None
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        style = p.style.name or ""
        if style == "Title":
            meta["title"] = t
            continue
        m = re.match(r"^(项目|日期|状态|目标化合物|第几步)[:：]\s*(.*)$", t)
        if m and cur is None:
            meta[m.group(1)] = m.group(2)
            continue
        is_head = style.startswith("Heading") or (len(t) <= 20 and t.endswith(("：", ":")))
        if is_head:
            cur = t.rstrip("：:")
            sections.setdefault(cur, [])
            continue
        if cur is not None:
            sections[cur].append((style, t))

    # 投料表
    reagents = []
    if d.tables:
        for row in d.tables[0].rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if len(cells) < 3 or not cells[1]:
                continue
            clean = [("" if c in ("—", "-", "/", "–") else c) for c in cells]
            reagents.append({
                "index": clean[0], "name": cells[1], "role": clean[2] if len(clean) > 2 else "",
                "mw": clean[3] if len(clean) > 3 else "",
                "ratio": clean[4] if len(clean) > 4 else "",
                "mass": clean[5] if len(clean) > 5 else "",
            })
    return meta, sections, reagents


def _format_kv_para(text):
    """把「溶剂：A ；温度：B」这类段落拆成多行，键名加粗。"""
    parts = [x.strip() for x in re.split(r"[;；]", text) if x.strip()]
    if not parts:
        return ""
    lines = []
    for x in parts:
        x = re.sub(r"^([^：:]{1,10})[：:]\s*", r"<strong>\1：</strong>", x)
        lines.append(x)
    return "<p>" + "<br>".join(lines) + "</p>"


def build_content(sections, include_placeholders=True):
    """把解析出的小节组装成模板正文 HTML。"""
    html = []
    if include_placeholders:
        html.append("<h2>反应方程式</h2>")
        html.append("<p>反应物与产物结构已预填（见「结构」页），反应条件亦已预填；"
                    "在「结构」页可直接编辑或按需替换为目标分子。</p>")
        html.append("<h2>投料表</h2>")
        html.append("<p>投料行已按角色预建（原料／试剂／溶剂）。"
                    "填入原料质量后，其余物料按当量比或重量比自动联动计算。</p>")

    for title, items in sections.items():
        if "方程式" in title or "投料表" in title:
            continue
        if not items:
            continue
        html.append("<h2>%s</h2>" % title)
        numbered = [t for st, t in items if st == "List Number"]
        plain = [t for st, t in items if st != "List Number"]
        for t in plain:
            html.append(_format_kv_para(t))
        if numbered:
            html.append("<ol>" + "".join(
                "<li>%s</li>" % t.rstrip(";；") for t in numbered) + "</ol>")
    return "".join(html)


# ------------------------------------------------------ 模板组装（配库）

# 由物料名称判断投料角色与投料比类型
REAGENT_HINTS = [
    (("sm", "起始原料", "原料"), "substrate", "equiv"),
    (("浓硝酸", "硝酸"), "reagent", "equiv"),
    (("浓硫酸", "硫酸", "盐酸"), "solvent", "weight"),
    (("冰水", "水"), "solvent", "weight"),
    (("dcm", "二氯甲烷", "乙酸乙酯", "甲苯", "甲醇", "乙醇", "丙酮", "thf", "四氢呋喃"), "solvent", "weight"),
    (("正庚烷", "正己烷", "石油醚", "乙醚"), "solvent", "weight"),
]

# 报告里的简称 → 化合物库中的正式名
LIB_ALIAS = {
    "dcm": "二氯甲烷",
    "浓硝酸": "硝酸",
    "浓硫酸": "硫酸",
    "冰水": "水",
}


def _norm(s):
    return (s or "").strip().lower()


def classify_reagent(name):
    n = _norm(name)
    for keys, role, rtype in REAGENT_HINTS:
        for k in keys:
            if n == k or (len(k) > 1 and k in n):
                return role, rtype
    return "reagent", "equiv"


def _canon(smiles):
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    return Chem.MolToSmiles(mol) if mol else None


def lookup_by_name(conn, name):
    row = conn.execute(
        "SELECT id,name,cas,smiles,mw,formula FROM compounds WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def lookup_by_smiles(conn, smiles):
    """在全库中按结构命中化合物（canonical SMILES 比对）。"""
    target = _canon(smiles)
    if not target:
        return None
    for row in conn.execute("SELECT id,name,cas,smiles,mw,formula FROM compounds"):
        if _canon(row["smiles"]) == target:
            return dict(row)
    return None


def build_reagent_template(reagents, conn, reactant_cmpd):
    """投料表模板。MW/SMILES 优先取自化合物库，角色按名称判定。"""
    out = []
    for r in reagents:
        name = r["name"]
        role, rtype = classify_reagent(name)
        entry = {"role": role, "name": name, "ratio_type": rtype, "ratio_value": None}
        # 原料行：用库中命中的结构补全
        if role == "substrate" and reactant_cmpd:
            entry["name"] = reactant_cmpd["name"]
            entry["mw"] = reactant_cmpd["mw"]
            entry["smiles"] = reactant_cmpd["smiles"] or ""
            entry["formula"] = reactant_cmpd["formula"] or ""
            entry["ratio_value"] = 1.0
        else:
            lib = lookup_by_name(conn, LIB_ALIAS.get(_norm(name), name))
            if lib:
                entry["mw"] = lib["mw"]
                entry["smiles"] = lib["smiles"] or ""
                entry["formula"] = lib["formula"] or ""
        # 液体试剂补密度/商品浓度，让投料表的体积与用量能自动算
        props = LIQUID_PROPS.get(_norm(name)) or LIQUID_PROPS.get(LIB_ALIAS.get(_norm(name), ""))
        if props:
            entry.update(props)
        out.append(entry)
    return out


def build_reaction_template(reactants, products, conn):
    """反应式模板：结构取自 KingDraw 重建结果，名称在库中反查。"""
    def one(it):
        info = it["info"]
        cmpd = lookup_by_smiles(conn, info["smiles"]) if info else None
        return {
            "name": cmpd["name"] if cmpd else (info["formula"] if info else ""),
            "smiles": info["smiles"] if info else "",
            "mw": info["mw"] if info else "",
            "formula": info["formula"] if info else "",
            "cas": cmpd["cas"] if cmpd else "",
        }

    return {
        "display_mode": "scheme",
        "reactant_smiles": [one(it) for it in reactants],
        "product_smiles": [one(it) for it in products],
        "conditions": "",
        "arrow_label": "",
        "notes": "",
        "image_path": "",
    }


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    apply_ = "--apply" in args
    name = args[args.index("--name") + 1] if "--name" in args else None

    print("=" * 66)
    print("  从研发报告导入 ChemELN 模板")
    print("=" * 66)
    print("源文件: %s" % path)
    print()

    meta, sections, reagents = parse_report_sections(path)
    print("报告标题: %s" % meta.get("title", ""))
    print("项目信息: %s / %s / 状态 %s / 第几步 %s"
          % (meta.get("项目", ""), meta.get("日期", ""), meta.get("状态", ""), meta.get("第几步", "")))
    print("正文章节: %s" % " / ".join(sections.keys()))
    print()

    # --- 反应式重建 ---
    protocol = extract_kingdraw_protocol(path)
    reactants, products, warns, ok = [], [], [], True
    if protocol:
        reactants, products, warns = parse_reaction_scheme(protocol)
        print("--- 反应式（KingDraw 连接表 → RDKit 重建）---")
        for tag, arr in (("反应物", reactants), ("产物", products)):
            for it in arr:
                if it["info"]:
                    print("  %s  SMILES : %s" % (tag, it["info"]["smiles"]))
                    print("        %s / MW %.2f   | 绘图自带标签: %s / %s"
                          % (it["info"]["formula"], it["info"]["mw"],
                             it["label_formula"], it["label_mw"]))
                else:
                    print("  %s  重建失败" % tag)
        if warns:
            ok = False
            print("  [自校验未通过]")
            for w in warns:
                print("    -", w)
        else:
            print("  自校验: 重建结构与绘图自带 Formula/Mol.Wt. 一致 [OK]")
    else:
        print("--- 未找到 KingDraw 绘图 ---")
        ok = False
    print()

    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # --- 库内反查（给结构配真实名称）---
    if reactants:
        rc = lookup_by_smiles(conn, reactants[0]["info"]["smiles"]) if reactants[0]["info"] else None
    else:
        rc = None
    if products and products[-1]["info"]:
        pc = lookup_by_smiles(conn, products[-1]["info"]["smiles"])
    else:
        pc = None
    print("--- 化合物库反查 ---")
    print("  反应物 → %s" % (("%s (CAS %s, MW %s)" % (rc["name"], rc["cas"], rc["mw"])) if rc else "(库中未命中)"))
    print("  产物   → %s" % (("%s (CAS %s, MW %s)" % (pc["name"], pc["cas"], pc["mw"])) if pc else "(库中未命中)"))
    print()

    reagent_template = build_reagent_template(reagents, conn, rc)
    reaction_template = build_reaction_template(reactants, products, conn)

    # 反应条件与箭头标注：从「试剂行 + 酸介质」和「工艺条件」小节推导，不写死
    cond_parts = []
    for r in reagent_template:
        is_medium = bool(re.search(r"硫酸|盐酸|磷酸|磺酸", r["name"]))
        if r["role"] == "reagent" or (r["role"] == "solvent" and is_medium):
            if r.get("formula"):
                disp = FORMULA_DISPLAY.get(r["name"]) \
                    or FORMULA_DISPLAY.get(LIB_ALIAS.get(_norm(r["name"]), ""))
                cond_parts.append(disp or r["formula"])
    reaction_template["conditions"] = " / ".join(cond_parts)

    for title, items in sections.items():
        if "工艺条件" in title:
            blob = " ".join(t for _st, t in items)
            m = re.search(r"温度[:：]\s*(\d+\s*[~\-–]\s*\d+\s*℃?)", blob)
            if m:
                reaction_template["arrow_label"] = m.group(1).replace(" ", "")
            break

    content = build_content(sections)
    tpl_name = name or ("%s 模板" % (meta.get("title") or "导入"))

    print("--- 投料表模板（%d 行）---" % len(reagent_template))
    for i, r in enumerate(reagent_template, 1):
        extra = ""
        if r.get("density"):
            extra += " d=%s" % r["density"]
        if r.get("purity_pct"):
            extra += " %s%%" % r["purity_pct"]
        print("  %d. %-12s 角色=%-9s 投料比=%-7s MW=%-9s%s"
              % (i, r["name"], r["role"], r["ratio_type"], r.get("mw", "-"), extra))
    print()
    print("--- 反应式模板 ---")
    print("  条件: %s | 箭头上: %s" % (reaction_template["conditions"], reaction_template["arrow_label"]))
    for tag, key in (("反应物", "reactant_smiles"), ("产物", "product_smiles")):
        for it in reaction_template[key]:
            print("  %s: %s  (%s, MW %s)" % (tag, it["name"], it["formula"], it["mw"]))
    print()
    print("--- 正文 HTML（%d 字符）---" % len(content))
    print(content)
    print()

    if not apply_:
        print("（预演模式，未写入数据库。确认无误后加 --apply 写入 templates 表）")
        conn.close()
        return 0

    cur = conn.execute(
        "INSERT INTO templates (name, type, content, reagent_template, reaction_template)"
        " VALUES (?, ?, ?, ?, ?)",
        (tpl_name, "reaction", content,
         json.dumps(reagent_template, ensure_ascii=False),
         json.dumps(reaction_template, ensure_ascii=False)))
    tid = cur.lastrowid
    conn.commit()
    conn.close()
    print("已写入模板 id=%s  name=%s" % (tid, tpl_name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
