#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从单一数据源生成前端 TS 与后端 Python 两份化学数据模块。

背景
----
整合前，化学数据在两处各维护一份，改一边就不同步：

    工具箱  src/data/solvents.ts            98 种溶剂，16 字段（物性详表）
    chemELN backend/utils/common_reagents.py  175 种试剂，4 字段（名称+分子式+CAS）

本次合并为 **193 个唯一 CAS**，字段取并集（19 个）。

架构
----
    shared/chemistry-data.json      ← 唯一手改的数据源（单一真源）
              │
              ├─→ src/data/solvents.ts              前端用（Vite import）
              └─→ backend/utils/common_reagents.py  后端用（MW 查询/播种）

**改数据只改 JSON**，然后跑本脚本重新生成两侧。不要在生成的 .ts/.py 里手改。

用法
----
    python scripts/build_chemistry_data.py            # 生成两侧
    python scripts/build_chemistry_data.py --check    # 只校验不写入
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "shared" / "chemistry-data.json"
TS_PATH = ROOT / "src" / "data" / "solvents.ts"
PY_PATH = ROOT / "backend" / "utils" / "common_reagents.py"

# 字段顺序（决定 JSON 与生成代码的展示顺序）
FIELDS = [
    "name",        # 中文名（主名）
    "en",          # 英文名/缩写
    "formula",     # 分子式
    "cas",         # CAS 号（唯一标识）
    "bp",          # 沸点 °C
    "density",     # 密度 g/mL (20°C)
    "polarity",    # 极性归类
    "dielectric",  # 介电常数 ε
    "miscible",    # 与水是否完全混溶
    "solubility",  # 水中溶解度说明
    "flash",       # 闪点 °C
    "risk",        # 管制/危害类别
    "hazard",      # 毒性/危害提示
    "use",         # 常见用途
    "desiccant",   # 常用除水/干燥方式
    "aliases",     # 别名/英文缩写（chemELN 侧带入，前端搜索也用得上）
]

# 前端需要但后端不需要的「溶剂物性」字段
SOLVENT_ONLY = {"bp", "density", "polarity", "dielectric", "miscible",
                "solubility", "flash", "hazard", "use", "desiccant", "risk", "en"}


def load_json() -> dict:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if "chemicals" not in data:
        raise SystemExit(f"{JSON_PATH} 缺少 chemicals 键")
    return data


# 极性基础分类白名单（前端筛选器只用这 4 个值）。
# 原数据里有「弱极性(非质子)」「极性非质子(碱)」等带细化的写法，
# 生成时拆成 polarity（基础分类）+ polarity_note（括号里的细化说明），
# 这样前端下拉筛选只需 4 项，同时不丢失原有信息。
POLARITY_BASE = ("非极性", "弱极性", "极性非质子", "极性质子")


def split_polarity(raw: str):
    """把「弱极性(非质子)」拆成 ('弱极性', '非质子')。

    无法识别基础分类时返回 (raw, '')，交由校验报错。
    """
    if not raw:
        return "", ""
    if "(" in raw and raw.endswith(")"):
        base, note = raw.split("(", 1)
        base, note = base.strip(), note[:-1].strip()
        if base in POLARITY_BASE:
            return base, note
        return raw, ""
    return raw.strip(), ""


def validate(data: dict) -> list[str]:
    """校验数据质量，返回错误列表（空 = 通过）。"""
    errors = []
    seen_cas = {}
    seen_name = {}
    for i, c in enumerate(data["chemicals"]):
        tag = f"#{i} {c.get('name', '?')}"
        cas = (c.get("cas") or "").strip()
        name = (c.get("name") or "").strip()
        if not name:
            errors.append(f"{tag}: name 为空")
        if not cas:
            errors.append(f"{tag}: cas 为空")
        else:
            if cas in seen_cas:
                errors.append(f"{tag}: CAS {cas} 与 #{seen_cas[cas]} 重复")
            seen_cas[cas] = i
        if not (c.get("formula") or "").strip():
            errors.append(f"{tag}: formula 为空")
        # 数值字段类型
        for f in ("bp", "density", "dielectric", "flash"):
            v = c.get(f)
            if v is not None and not isinstance(v, (int, float)):
                errors.append(f"{tag}: {f} 应为数值或 null，实为 {type(v).__name__}")
        if not isinstance(c.get("miscible", False), bool):
            errors.append(f"{tag}: miscible 应为布尔")
        if not isinstance(c.get("risk", []), list):
            errors.append(f"{tag}: risk 应为数组")
        # 极性归类白名单
        pol = c.get("polarity")
        if pol and pol not in POLARITY_BASE:
            errors.append(f"{tag}: polarity '{pol}' 不在白名单 {POLARITY_BASE}")
        if name:
            if name in seen_name:
                errors.append(f"{tag}: name '{name}' 与 #{seen_name[name]} 重复")
            seen_name[name] = i
    return errors


def gen_ts(data: dict) -> str:
    """生成 src/data/solvents.ts。"""
    chems = data["chemicals"]
    lines = [
        "// ============================================================",
        "// solvents.ts —— 常用溶剂/试剂物性数据（纯数据，无逻辑）",
        "//",
        "// ⚠️ 本文件由 scripts/build_chemistry_data.py 自动生成，请勿手改！",
        "//    数据源：shared/chemistry-data.json",
        f"//    生成时间：{data['meta']['generated_at']}",
        f"//    条目数：{len(chems)}（CAS 唯一）",
        "//",
        "// 字段来源：",
        "//   物性字段（沸点/密度/极性/介电常数/水溶性/闪点/危害/干燥/管制）",
        "//     源自用户《常用溶剂物性表.xlsx》权威表（工具箱侧，2026-09-24）",
        "//   名称/别名/分子式/CAS",
        "//     源自 chemELN common_reagents.py（整合时并入）",
        "//",
        "// 实际使用请以试剂瓶标签、最新 SDS 与最新版名录为准；",
        "// 本数据仅作查询参考。",
        "// ============================================================",
        "",
        "export interface SolventInfo {",
        "  name: string;         // 中文名",
        "  en: string;           // 英文名/缩写",
        "  formula: string;      // 分子式",
        "  cas: string;          // CAS 号（唯一标识）",
        "  bp: number | null;    // 沸点 °C（常压参考值，null=无记录）",
        "  density: number | null; // 密度 g/mL（20°C 参考值）",
        "  polarity: string;     // 极性基础归类（非极性/弱极性/极性非质子/极性质子）",
        "  polarityNote: string; // 极性细化说明（如「非质子」「碱」「强H键供体」，来自原数据括号内容）",
        "  dielectric: number | null; // 介电常数 ε（null=无记录）",
        "  miscible: boolean;    // 与水是否完全混溶",
        "  solubility: string;   // 水中溶解度说明",
        "  flash: number | null; // 闪点 °C（null = 无闪点/不易燃）",
        "  risk: string[];       // 管制/危害类别",
        "  hazard: string;       // 毒性/危害提示（公开常识/手册，非操作指导）",
        "  use: string;          // 常见用途",
        "  desiccant: string;    // 常用除水/干燥方式",
        "  aliases: string[];    // 别名/英文缩写（chemELN 侧带入，便于搜索）",
        "}",
        "",
        "export const SOLVENTS: SolventInfo[] = [",
    ]

    for c in chems:
        polarity, polarity_note = split_polarity(c.get("polarity", ""))

        def jv(key, default=None):
            v = c.get(key, default)
            return json.dumps(v, ensure_ascii=False)

        lines.append("  {")
        lines.append(f'    name: {jv("name")}, en: {jv("en", "")}, formula: {jv("formula")}, cas: {jv("cas")},')
        lines.append(
            f'    bp: {c.get("bp") if c.get("bp") is not None else "null"}, '
            f'density: {c.get("density") if c.get("density") is not None else "null"}, '
            f'polarity: {json.dumps(polarity, ensure_ascii=False)}, '
            f'polarityNote: {json.dumps(polarity_note, ensure_ascii=False)}, '
            f'dielectric: {c.get("dielectric") if c.get("dielectric") is not None else "null"},'
        )
        lines.append(
            f'    miscible: {"true" if c.get("miscible") else "false"}, '
            f'solubility: {jv("solubility", "")}, '
            f'flash: {c.get("flash") if c.get("flash") is not None else "null"},'
        )
        lines.append(f'    risk: {json.dumps(c.get("risk", []), ensure_ascii=False)},')
        lines.append(f'    hazard: {jv("hazard", "")},')
        lines.append(f'    use: {jv("use", "")},')
        lines.append(f'    desiccant: {jv("desiccant", "")},')
        lines.append(f'    aliases: {json.dumps(c.get("aliases", []), ensure_ascii=False)},')
        lines.append("  },")

    lines.append("];")
    lines.append("")
    lines.append("/** 按 CAS 快速查找（CAS 是唯一标识）。 */")
    lines.append("export const SOLVENT_BY_CAS: Record<string, SolventInfo> =")
    lines.append("  Object.fromEntries(SOLVENTS.map((s) => [s.cas, s]));")
    lines.append("")
    lines.append("/** 按中文名/英文名/别名模糊匹配，用于搜索框联想。 */")
    lines.append("function shortName(name: string): string {")
    lines.append("  // 「乙醇(EtOH)」→「乙醇」：合并后的 name 常带英文缩写后缀，")
    lines.append("  // 但用户输入「乙醇」时也应能匹配到。")
    lines.append("  const i = name.indexOf('(');")
    lines.append("  return i > 0 ? name.slice(0, i).trim() : name.trim();")
    lines.append("}")
    lines.append("")
    lines.append("export function findSolvents(keyword: string, limit = 20): SolventInfo[] {")
    lines.append("  const k = keyword.trim().toLowerCase();")
    lines.append("  if (!k) return [];")
    lines.append("  const hit = (s: SolventInfo) =>")
    lines.append("    s.name.toLowerCase().includes(k) ||")
    lines.append("    shortName(s.name).toLowerCase().includes(k) ||")
    lines.append("    s.en.toLowerCase().includes(k) ||")
    lines.append("    s.cas.includes(k) ||")
    lines.append("    s.formula.toLowerCase().includes(k) ||")
    lines.append("    s.aliases.some((a) => a.toLowerCase().includes(k));")
    lines.append("  const exact = SOLVENTS.filter(")
    lines.append("    (s) =>")
    lines.append("      s.name.toLowerCase() === k ||")
    lines.append("      s.en.toLowerCase() === k ||")
    lines.append("      shortName(s.name).toLowerCase() === k ||")
    lines.append("      s.aliases.some((a) => a.toLowerCase() === k),")
    lines.append("  );")
    lines.append("  const partial = SOLVENTS.filter(")
    lines.append("    (s) =>")
    lines.append("      s.name.toLowerCase() !== k &&")
    lines.append("      s.en.toLowerCase() !== k &&")
    lines.append("      shortName(s.name).toLowerCase() !== k &&")
    lines.append("      !s.aliases.some((a) => a.toLowerCase() === k) &&")
    lines.append("      hit(s),")
    lines.append("  );")
    lines.append("  return [...exact, ...partial].slice(0, limit);")
    lines.append("}")
    lines.append("")
    lines.extend(
        [
            "/** 列表页搜索：中文名 / 英文名 / CAS / 分子式 / 用途 / 别名 模糊匹配。",
            " *  空关键词返回全表（保持旧版 searchSolvents 行为）。",
            " */",
            "export function searchSolvents(keyword: string): SolventInfo[] {",
            "  const k = keyword.trim().toLowerCase();",
            "  if (!k) return SOLVENTS;",
            "  return SOLVENTS.filter(",
            "    (s) =>",
            "      s.name.toLowerCase().includes(k) ||",
            "      shortName(s.name).toLowerCase().includes(k) ||",
            "      s.en.toLowerCase().includes(k) ||",
            "      s.formula.toLowerCase().includes(k) ||",
            "      s.cas.toLowerCase().includes(k) ||",
            "      s.use.toLowerCase().includes(k) ||",
            "      s.aliases.some((a) => a.toLowerCase().includes(k)),",
            "  );",
            "}",
            "",
            "/** 徽章样式类：按管制/危害类别返回 CSS 类名。",
            " *  易制毒/易制爆=红（管制最严） / 过氧化物易爆=紫 / 有毒=橙",
            " */",
            "export function riskClass(risk: string): string {",
            '  if (risk.startsWith("易制毒") || risk.startsWith("易制爆")) return "risk-yz";',
            '  if (risk.includes("过氧化物")) return "risk-po";',
            '  return "risk-tox";',
            "}",
            "",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 后端模块固定尾部（逻辑部分，不随数据变化）
#
# 这里保留了 chemELN 原 common_reagents.py 的公共 API，缺一不可：
#   - formula_mw()              由分子式算 MW（不依赖 rdkit，纯内置实现）
#   - lookup_common_reagent()   routers/compounds.py:11 直接 import，删了后端起不来
#   - get_seeded_common_compounds()  database.py:47 播种用
# 只生成数据、把逻辑丢掉会导致 ImportError，务必同步维护。
# ---------------------------------------------------------------------------
PY_RUNTIME = '''
# ---------------------------------------------------------------- 分子量计算
# Atomic weights for formula parsing
ATOMIC_WEIGHTS = {
    "H": 1.008, "D": 2.014, "He": 4.003, "Li": 6.94, "Be": 9.012,
    "B": 10.81, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998,
    "Ne": 20.180, "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085,
    "P": 30.974, "S": 32.06, "Cl": 35.45, "Ar": 39.948, "K": 39.098,
    "Ca": 40.078, "Ti": 47.867, "V": 50.942, "Cr": 51.996, "Mn": 54.938,
    "Fe": 55.845, "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38,
    "Ga": 69.723, "Ge": 72.630, "As": 74.922, "Se": 78.971, "Br": 79.904,
    "Kr": 83.798, "Rb": 85.468, "Sr": 87.62, "Y": 88.906, "Zr": 91.224,
    "Nb": 92.906, "Mo": 95.95, "Ru": 101.07, "Rh": 102.91, "Pd": 106.42,
    "Ag": 107.87, "Cd": 112.41, "In": 114.82, "Sn": 118.71, "Sb": 121.76,
    "Te": 127.60, "I": 126.90, "Xe": 131.29, "Cs": 132.91, "Ba": 137.33,
    "La": 138.91, "Ce": 140.12, "Eu": 151.96, "Yb": 173.05, "Lu": 174.97,
    "Hf": 178.49, "Ta": 180.95, "W": 183.84, "Re": 186.21, "Os": 190.23,
    "Ir": 192.22, "Pt": 195.08, "Au": 196.97, "Hg": 200.59, "Tl": 204.38,
    "Pb": 207.2, "Bi": 208.98, "Th": 232.04, "U": 238.03,
}


def formula_mw(formula: str):
    """Compute molecular weight from a chemical formula string.

    Supports parentheses and hydrate dots, e.g. CuSO4.5H2O, Fe2(SO4)3.
    Returns float or None if unparseable.
    """
    if not formula:
        return None
    formula = formula.strip()

    def parse_segment(seg):
        total = 0.0
        i = 0
        while i < len(seg):
            ch = seg[i]
            if ch in "([":
                depth = 1
                j = i + 1
                while j < len(seg) and depth > 0:
                    if seg[j] in "([":
                        depth += 1
                    elif seg[j] in ")]":
                        depth -= 1
                    j += 1
                if depth != 0:
                    return None
                inner = parse_segment(seg[i + 1:j - 1])
                if inner is None:
                    return None
                # count following digits
                k = j
                num = ""
                while k < len(seg) and seg[k].isdigit():
                    num += seg[k]
                    k += 1
                total += inner * (int(num) if num else 1)
                i = k
            elif ch.isupper():
                sym = ch
                j = i + 1
                while j < len(seg) and seg[j].islower():
                    sym += seg[j]
                    j += 1
                if sym not in ATOMIC_WEIGHTS:
                    return None
                num = ""
                while j < len(seg) and (seg[j].isdigit() or seg[j] == "."):
                    if seg[j] == "." and not seg[j:j + 1].isdigit():
                        break
                    num += seg[j]
                    j += 1
                total += ATOMIC_WEIGHTS[sym] * (float(num) if num else 1.0)
                i = j
            else:
                return None
        return total

    # Split hydrates: CuSO4·5H2O / CuSO4.5H2O / Na2O.Al2O3.2SiO2
    total = 0.0
    for sep in ("·", "*"):
        formula = formula.replace(sep, ".")
    parts = formula.split(".")
    for idx, part in enumerate(parts):
        part = part.strip()
        if not part:
            return None
        # hydrate multiplier: leading integer
        mult = 1
        j = 0
        while j < len(part) and part[j].isdigit():
            j += 1
        if j > 0 and j < len(part) and part[j].isupper():
            mult = int(part[:j])
            part = part[j:]
        seg_mw = parse_segment(part)
        if seg_mw is None:
            return None
        total += seg_mw * mult

    return round(total, 3) if total > 0 else None


def _build_index():
    """Build alias -> entry lookup (lowercased)."""
    index = {}
    for name, aliases, formula, cas in COMMON_REAGENTS:
        entries = [name] + list(aliases)
        # 主名（去括号后缀）也进索引，保证「乙醇」能命中「乙醇(EtOH)」
        sn = _short_name(name)
        if sn:
            entries.append(sn)
        for a in entries:
            key = a.strip().lower()
            if key and key not in index:
                index[key] = (name, formula, cas)
    return index


_ALIAS_INDEX = _build_index()


def lookup_common_reagent(query: str):
    """Look up a reagent by name/alias/formula. Returns dict or None."""
    q = (query or "").strip()
    if not q:
        return None
    key = q.lower()
    # 1. exact alias match
    if key in _ALIAS_INDEX:
        name, formula, cas = _ALIAS_INDEX[key]
        mw = formula_mw(formula)
        if mw:
            return {"found": True, "source": "common", "name": name,
                    "formula": formula, "mw": mw, "cas": cas}
    # 2. try as a bare chemical formula, e.g. K2CO3, FeCl3, CuSO4.5H2O
    if any(c.isdigit() for c in q) and any(c.isalpha() for c in q):
        mw = formula_mw(q)
        if mw:
            return {"found": True, "source": "formula", "name": q,
                    "formula": q, "mw": mw, "cas": ""}
    # 3. partial match (contains), only for aliases of decent length
    for k, (name, formula, cas) in _ALIAS_INDEX.items():
        if len(k) >= 3 and len(key) >= 3 and (key in k or k in key):
            mw = formula_mw(formula)
            if mw:
                return {"found": True, "source": "common", "name": name,
                        "formula": formula, "mw": mw, "cas": cas}
    return None


def get_seeded_common_compounds():
    """Return built-in solvent/reagent entries as seed rows.

    Each row: (name, cas, formula, mw, category)
    category is 'solvent' if the CAS carries 物性数据（源自工具箱溶剂表）,
    otherwise 'reagent'.
    """
    rows = []
    for name, aliases, formula, cas in COMMON_REAGENTS:
        mw = formula_mw(formula)
        if mw is None:
            continue
        category = "solvent" if cas in SOLVENT_CAS else "reagent"
        rows.append((name, cas, formula, mw, category))
    return rows


if __name__ == "__main__":
    tests = ["乙醇", "NaOH", "K2CO3", "苯硼酸", "DCM", "MeOH", "Pd(PPh3)4",
             "CuSO4.5H2O", "Fe2(SO4)3", "THF", "HATU", "nabh4", "水"]
    for t in tests:
        print(f"{t:15s} =>", lookup_common_reagent(t))
'''


def gen_py(data: dict) -> str:
    """生成 backend/utils/common_reagents.py。"""
    chems = data["chemicals"]
    lines = [
        '"""',
        "Built-in common reagent dictionary for MW lookup.",
        "Maps common reagent names (Chinese / English / abbreviation) to chemical formulas.",
        "MW is computed from the formula via formula_mw().",
        "",
        "⚠️ 本文件由 scripts/build_chemistry_data.py 自动生成，请勿手改！",
        "    数据源：shared/chemistry-data.json",
        f"    生成时间：{data['meta']['generated_at']}",
        f"    条目数：{len(chems)}（CAS 唯一，含溶剂物性详表 + chemELN 试剂库合并）",
        '"""',
        "",
        "# (name, aliases, formula, cas)",
        "COMMON_REAGENTS = [",
    ]
    for c in chems:
        aliases = json.dumps(c.get("aliases", []), ensure_ascii=False)
        lines.append(
            f'    ({json.dumps(c["name"], ensure_ascii=False)}, {aliases}, '
            f'{json.dumps(c["formula"], ensure_ascii=False)}, {json.dumps(c["cas"], ensure_ascii=False)}),'
        )
    lines.append("]")
    lines.append("")
    # 溶剂判定：带物性数据（polarity 非空）的条目来自工具箱《常用溶剂物性表》，
    # 纯试剂条目 polarity 为空。用 CAS 集合而非中文名，避免合并后改名失配。
    solvent_cas = sorted({c["cas"] for c in chems if c.get("polarity")})
    lines.append("# ---------------------------------------------------------------- 分类")
    lines.append("# 是否溶剂：以 CAS 是否带物性数据判定（物性源自工具箱溶剂表；")
    lines.append("# 纯试剂条目 polarity/bp/density 均为空）。用 CAS 而非中文名，")
    lines.append("# 避免「乙醇」→「乙醇(EtOH)」这类合并改名导致失配。")
    lines.append(f"# 溶剂 {len(solvent_cas)} 种 / 共 {len(chems)} 种")
    lines.append("SOLVENT_CAS = {")
    for i in range(0, len(solvent_cas), 6):
        chunk = ", ".join(json.dumps(x, ensure_ascii=False) for x in solvent_cas[i:i + 6])
        lines.append(f"    {chunk},")
    lines.append("}")
    lines.append("")
    lines.append("# ---------------------------------------------------------------- 索引")
    lines.append("")
    lines.append("_BY_CAS = {r[3]: r for r in COMMON_REAGENTS}")
    lines.append("_BY_NAME = {r[0]: r for r in COMMON_REAGENTS}")
    lines.append("_BY_ALIAS = {}")
    lines.append("")
    lines.append("")
    lines.append("def _short_name(name: str) -> str:")
    lines.append('    """取括号前的主名：「乙醇(EtOH)」→「乙醇」。')
    lines.append("")
    lines.append("    合并后的 name 常带英文缩写后缀（源自工具箱的命名习惯），")
    lines.append("    但用户输入「乙醇」时也应能查到，因此主名单独建索引。")
    lines.append('    """')
    lines.append("    if \"(\" in name:")
    lines.append("        return name.split(\"(\", 1)[0].strip()")
    lines.append("    return name.strip()")
    lines.append("")
    lines.append("")
    lines.append("for _r in COMMON_REAGENTS:")
    lines.append("    for _a in _r[1]:")
    lines.append("        _BY_ALIAS.setdefault(_a.lower(), _r)")
    lines.append("    # 主名（去括号后缀）也纳入别名索引，大小写不敏感")
    lines.append("    _sn = _short_name(_r[0])")
    lines.append("    if _sn:")
    lines.append("        _BY_ALIAS.setdefault(_sn.lower(), _r)")
    lines.append("")
    lines.append("")
    lines.append("def get_reagent(key: str):")
    lines.append('    """按中文名/英文/别名/CAS 查找试剂，返回 (name, aliases, formula, cas) 或 None。')
    lines.append("")
    lines.append("    匹配顺序：CAS → 完整名 → 别名/主名（大小写不敏感）。")
    lines.append('    """')
    lines.append("    if not key:")
    lines.append("        return None")
    lines.append("    k = key.strip()")
    lines.append("    if k in _BY_CAS:")
    lines.append("        return _BY_CAS[k]")
    lines.append("    if k in _BY_NAME:")
    lines.append("        return _BY_NAME[k]")
    lines.append("    low = k.lower()")
    lines.append("    if low in _BY_ALIAS:")
    lines.append("        return _BY_ALIAS[low]")
    lines.append("    return None")
    lines.append("")
    lines.append("")
    lines.append(PY_RUNTIME.rstrip("\n"))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="从 JSON 单一源生成前端/后端化学数据模块")
    ap.add_argument("--check", action="store_true", help="只校验不写入")
    args = ap.parse_args()

    if not JSON_PATH.exists():
        print(f"错误: 数据源不存在 {JSON_PATH}")
        return 1

    data = load_json()

    # 1. 校验
    errors = validate(data)
    if errors:
        print(f"数据校验失败（{len(errors)} 处）:")
        for e in errors[:30]:
            print("  -", e)
        return 1
    print(f"校验通过: {len(data['chemicals'])} 条，CAS 唯一，字段类型正确")

    if args.check:
        return 0

    # 2. 生成
    ts = gen_ts(data)
    py = gen_py(data)

    TS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PY_PATH.parent.mkdir(parents=True, exist_ok=True)
    TS_PATH.write_text(ts, encoding="utf-8")
    PY_PATH.write_text(py, encoding="utf-8")

    print(f"已生成 {TS_PATH}  ({len(ts.splitlines())} 行)")
    print(f"已生成 {PY_PATH}  ({len(py.splitlines())} 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
