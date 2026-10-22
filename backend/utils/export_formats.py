# -*- coding: utf-8 -*-
"""
ChemELN — Word (.docx) 与 PDF 导出。

Word: python-docx 结构化生成（标题/元信息/反应式/投料表/正文/附件）
PDF : xhtml2pdf 渲染（注册 Windows 中文字体，表格布局，base64 结构图内嵌）
"""
import base64
import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime

from bs4 import BeautifulSoup, NavigableString

from utils.export import (DB_PATH, ATTACH_DIR, BACKUP_DIR,
                          FONT_LATIN, FONT_CJK, FONT_SYMBOL,
                          attachment_abs_path, attachment_data_uri,
                          strip_inline_fonts, fmt_quantity)
from utils.chem import render_structure_image

ROLE_NAMES = {"substrate": "原料", "reagent": "试剂", "solvent": "溶剂", "product": "产物"}

# Windows 字体目录（Times New Roman / 宋体 / Segoe UI Symbol 都在这里）
_WIN_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


# ------------------------------------------------------------------ PDF 字体
# 导出统一「西文 Times New Roman + 中文 宋体」。
#
# ⛔ 关键差异：xhtml2pdf 的 font-family **不能像浏览器那样逐字符回退** ——
#    pisaContext.getFontName() 只是按逗号顺序取「第一个已注册」的字体名，整段文字
#    都用它。所以「Times 排版西文 + 宋体排版中文」必须靠 HTML 结构来表达：
#    正文用 Times，中文片段单独包 <span class="f-cjk">。
#    （实测：不做包裹时，中文落在 Times 下会输出 \x00 空字形，PDF 里直接是空白。）
#
# 字体链：Times New Roman（真 TTF，PDF 内嵌）→ 宋体 SimSun（TTF）→
#         Segoe UI Symbol（兜底符号：⟶ ⇌ ✕ ⚙ 等前两者都没有）
# 任何一款取不到都自动降级，不影响导出可用性。
_FONT_STATE = None


def _try_ttf(name, filename, subfont_index=0):
    """注册一个 TTF/TTC 字体，失败返回 None（不抛异常）。"""
    path = os.path.join(_WIN_FONTS, filename)
    if not os.path.isfile(path):
        return None
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        font = TTFont(name, path, subfontIndex=subfont_index)
        pdfmetrics.registerFont(font)
        return font
    except Exception:
        return None


def _register_fonts():
    """注册导出用字体，返回状态字典（进程内只做一次）。

    {'latin': 字体名, 'cjk': 字体名, 'sym': 字体名或 None,
     'cmap': {字体名: 支持的码位集合}}
    """
    global _FONT_STATE
    if _FONT_STATE is not None:
        return _FONT_STATE

    state = {"latin": "Times-Roman", "cjk": None, "sym": None, "cmap": {}}
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ImportError:
        _FONT_STATE = state
        return state

    # 1) 西文：真 Times New Roman（四个字重一起注册，粗体/斜体才映射得对）
    faces = {
        "Times New Roman": "times.ttf",
        "Times New Roman,Bold": "timesbd.ttf",
        "Times New Roman,Italic": "timesi.ttf",
        "Times New Roman,BoldItalic": "timesbi.ttf",
    }
    got = {nm: _try_ttf(nm, fn) for nm, fn in faces.items()}
    if all(got.values()):
        try:
            pdfmetrics.registerFontFamily(
                "Times New Roman",
                normal="Times New Roman", bold="Times New Roman,Bold",
                italic="Times New Roman,Italic",
                boldItalic="Times New Roman,BoldItalic")
        except Exception:
            pass
        state["latin"] = "Times New Roman"
        state["cmap"]["Times New Roman"] = set(got["Times New Roman"].face.charToGlyph)
    # 取不到就用 reportlab 内置的 Times-Roman（base-14，不内嵌，字形同源）

    # 2) 中文：宋体 SimSun（TTF）；取不到退回 Adobe 标准 CID 字体
    ss = _try_ttf("SimSun", "simsun.ttc", subfont_index=0)
    if ss:
        state["cjk"] = "SimSun"
        state["cmap"]["SimSun"] = set(ss.face.charToGlyph)
    else:
        for name in ("STSong-Light", "STSongStd-Light"):
            try:
                pdfmetrics.registerFont(UnicodeCIDFont(name))
                state["cjk"] = name
                break
            except Exception:
                continue

    # 3) 符号兜底：Segoe UI Symbol（⟶ U+27F6、⇌、✕ 等 Times/宋体都没有）
    sym = _try_ttf("Segoe UI Symbol", "seguisym.ttf")
    if sym:
        state["sym"] = "Segoe UI Symbol"
        state["cmap"]["Segoe UI Symbol"] = set(sym.face.charToGlyph)

    # 4) 挂进 xhtml2pdf 的字体表（pisaContext 创建时 copy 的是这个 dict）
    try:
        import xhtml2pdf.default as _x2default
        _x2default.DEFAULT_FONT.update({
            "times new roman": state["latin"],
            "serif": state["latin"],
            "simsun": state["cjk"],
            "宋体": state["cjk"],
            "segoe ui symbol": state["sym"] or state["cjk"],
        })
    except Exception:
        pass

    _FONT_STATE = state
    return state


def _font_css(state) -> str:
    """生成 PDF 的字体 CSS（元素列表 + 中文/符号两类 span）。"""
    css = (", ".join([
        "body", "h1", "h2", "h3", "h4", "p", "div", "li", "dt", "dd",
        "td", "th", "span", "b", "i", "u", "em", "strong", "code", "pre",
        "blockquote", "a", "small", "sub", "sup", "ul", "ol", "table",
    ]) + f' {{ font-family: "{state["latin"]}"; }}')
    if state["cjk"]:
        css += f'\n  span.f-cjk {{ font-family: "{state["cjk"]}"; }}'
    if state["sym"]:
        css += f'\n  span.f-sym {{ font-family: "{state["sym"]}"; }}'
    return css


# head/script 里的内容不是要渲染的文本，先摘出来，避免被包 span
_PROTECT_BLOCKS = re.compile(r"(<(?:head|script)\b[^>]*>.*?</(?:head|script)>)",
                             re.I | re.S)
_TAG_SPLIT = re.compile(r"(<[^>]*>)")

# Times New Roman 取不到、拿不到字符表时的兜底判据（base-14 只覆盖西文）
_NON_LATIN_FALLBACK = 0x0220

# 数字字符引用（&#10230; / &#x27F6;）
_NUMERIC_REF = re.compile(r"&#(?:(\d+)|[xX]([0-9a-fA-F]+));")


def _decode_numeric_refs(seg: str) -> str:
    """把 &#10230; 这类数字字符引用还原成真字符。

    ⛔ 必须还原：不还原的话，下面的「逐字符判定字体」看到的是 `&#10230;`
    这 8 个 ASCII 字符，会判定「Times 能渲染」；而真正渲染时它才变成 U+27F6，
    Times 没有该字形 → PDF 里输出空字形（反应箭头直接消失）。
    只还原非 ASCII（ASCII 引用保持原样，避免动到转义语义）。
    """
    def _sub(m):
        try:
            cp = int(m.group(1)) if m.group(1) else int(m.group(2), 16)
        except (TypeError, ValueError):
            return m.group(0)
        return chr(cp) if 0x80 <= cp <= 0x10FFFF else m.group(0)

    return _NUMERIC_REF.sub(_sub, seg)


def wrap_font_runs(html: str, state) -> str:
    """按字符覆盖情况，把文本切成若干段并套上对应字体的 span。

    xhtml2pdf 一个元素只能用一个字体，所以「同一段文字里西文用 Times、中文用宋体」
    只能落到 HTML 结构上：这里逐字符判定该用哪款字体，再把连续同款字符合成一个 span。
    （标签、属性一律不动 —— 按标签切开后只处理非标签片段。）
    """
    latin = state["latin"]
    cjk = state["cjk"]
    sym = state["sym"]
    cmap = state["cmap"]
    latin_cp = cmap.get(latin) or set()
    cjk_cp = (cmap.get(cjk) or set()) if cjk else set()
    sym_cp = (cmap.get(sym) or set()) if sym else set()

    def pick(ch):
        """返回该字符要用的 span class；None 表示用默认（Times New Roman）。"""
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF:      # 占位符（PUA）不参与
            return None
        if latin_cp:
            if cp in latin_cp:
                return None
            if cjk and cp in cjk_cp:
                return "f-cjk"
            if sym and cp in sym_cp:
                return "f-sym"
            return "f-cjk" if cjk else None   # 都不覆盖：交给宋体，至少不是空白
        # 没有字符表（如只拿到 base-14 Times-Roman）：按码位粗略判断
        if cp < _NON_LATIN_FALLBACK:
            return None
        if cjk and cp in cjk_cp:
            return "f-cjk"
        if sym and cp in sym_cp:
            return "f-sym"
        return "f-cjk" if cjk else None

    def wrap_text(text):
        runs = []
        for ch in text:
            cls = pick(ch)
            if runs and runs[-1][0] == cls:
                runs[-1][1].append(ch)
            else:
                runs.append((cls, [ch]))
        return "".join(
            f'<span class="{cls}">{"".join(chs)}</span>' if cls else "".join(chs)
            for cls, chs in runs)

    stashed = []

    def _stash(m):
        stashed.append(m.group(1))
        return f"\ue000{len(stashed) - 1}\ue001"

    html = _PROTECT_BLOCKS.sub(_stash, html)
    parts = _TAG_SPLIT.split(html)
    html = "".join(p if p.startswith("<") else wrap_text(_decode_numeric_refs(p))
                   for p in parts)
    return re.sub(r"\ue000(\d+)\ue001", lambda m: stashed[int(m.group(1))], html)


def font_status() -> dict:
    """导出字体的实际可用情况（供自助诊断调用）。

    不只报告注册结果，还真的渲一张最小 PDF 看字体有没有嵌进去 ——
    注册成功但没内嵌（或字形缺失）都会在最终文件里露馅。
    """
    st = _register_fonts()
    status = {"latin": st["latin"], "cjk": st["cjk"], "sym": st["sym"],
              "embedded": [], "error": ""}
    try:
        import io

        from xhtml2pdf import pisa
        html = (f'<!DOCTYPE html><html><head><meta charset="utf-8">'
                f'<style>{_font_css(st)}</style></head>'
                f'<body><p>Sample 字体检查 ABC 123</p></body></html>')
        buf = io.BytesIO()
        pisa.CreatePDF(wrap_font_runs(html, st), dest=buf, encoding="utf-8")
        raw = buf.getvalue()
        for name in ("TimesNewRoman", "SimSun", "STSong", "SegoeUISymbol"):
            if name.encode("ascii") in raw:
                status["embedded"].append(name)
    except Exception as e:
        status["error"] = f"{type(e).__name__}: {e}"
    return status



def _load_experiment(exp_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    exp = conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
    if not exp:
        conn.close()
        return None
    data = {
        "exp": dict(exp),
        "tags": [r["name"] for r in conn.execute(
            "SELECT t.name FROM tags t JOIN experiment_tags et ON t.id=et.tag_id "
            "WHERE et.experiment_id=?", (exp_id,))],
        "reagents": [dict(r) for r in conn.execute(
            "SELECT * FROM reagents WHERE experiment_id=? ORDER BY sort_order", (exp_id,))],
        "attachments": [dict(r) for r in conn.execute(
            "SELECT * FROM attachments WHERE experiment_id=?", (exp_id,))],
        "reaction": None,
        "compound": None,
    }
    rxn = conn.execute("SELECT * FROM reactions WHERE experiment_id=? ORDER BY id DESC LIMIT 1",
                       (exp_id,)).fetchone()
    if rxn:
        data["reaction"] = dict(rxn)
    if exp["fk_compound_id"]:
        c = conn.execute("SELECT * FROM compounds WHERE id=?", (exp["fk_compound_id"],)).fetchone()
        if c:
            data["compound"] = dict(c)
    conn.close()
    return data


def _ratio_text(r):
    if r["role"] == "substrate":
        return "基准"
    rv = r.get("ratio_value")
    if rv is None:
        rv = r.get("equivalents")
    if rv is None:
        return "—"
    return f"{rv} wt" if r.get("ratio_type") == "weight" else f"{rv} eq"


def _mass_text(r):
    """投料质量(g)：显示位数按 fmt_quantity 的大小规则（<0 → 3 位，0~10 → 2 位，≥10 → 1 位）"""
    mass = r.get("mass_g")
    if mass is None and r.get("mass_mg") is not None:
        mass = r["mass_mg"] / 1000.0
    return "—" if mass is None else fmt_quantity(mass)


def _mol_text(r):
    """摩尔(mmol)：重量比模式不算摩尔；其余按 fmt_quantity 的显示规则"""
    if r.get("ratio_type") == "weight":
        return "—"
    mol = r.get("moles_mmol")
    return "—" if mol is None else fmt_quantity(mol)


def _vol_text(r):
    """体积(mL)：重量比模式不算体积；其余按 fmt_quantity 的显示规则"""
    if r.get("ratio_type") == "weight":
        return "—"
    vol = r.get("volume_ml")
    return "—" if vol is None else fmt_quantity(vol)


def _reaction_items(reaction, tmpdir):
    """Render reaction structures to temp PNGs. Returns (reactants, products) lists."""
    def parse(s):
        try:
            return json.loads(s or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def build(items, prefix):
        out = []
        for i, it in enumerate(items):
            b64 = ""
            path = None
            if it.get("smiles"):
                try:
                    b64 = render_structure_image(it["smiles"], size=220)
                    path = os.path.join(tmpdir, f"{prefix}_{i}.png")
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(b64))
                except Exception:
                    b64, path = "", None
            meta = ""
            if it.get("mw"):
                meta = f'MW {it["mw"]}' + (f' · {it["formula"]}' if it.get("formula") else "")
            out.append({"name": it.get("name", ""), "meta": meta, "path": path, "b64": b64})
        return out

    return (build(parse(reaction.get("reactant_smiles")), "r"),
            build(parse(reaction.get("product_smiles")), "p"))


def _pdf_img_attrs(rel_path: str, max_w: int = 440) -> str:
    """给 PDF 里的 <img> 生成显式宽高属性。

    xhtml2pdf 对 max-width/max-height 支持不完整，只写 width 又会把像素按 72dpi
    当点处理（高分辨率 ChemDraw 图会撑爆页面），所以读原图尺寸等比缩放后写死。
    """
    full = attachment_abs_path(rel_path)
    w = h = None
    if full:
        try:
            from PIL import Image
            with Image.open(full) as im:
                w, h = im.size
        except Exception:
            w = h = None
    if not w or not h:
        return f'width="{max_w}"'
    if w > max_w:
        h = max(int(round(h * max_w / float(w))), 1)
        w = max_w
    return f'width="{w}" height="{h}"'


def _meta_rows(d):
    exp = d["exp"]
    rows = [
        ("项目", exp["project"] or "—"),
        ("日期", exp["exp_date"] or "—"),
        ("状态", exp["status"] or "—"),
        ("目标化合物", exp["target_compound"] or "—"),
        ("第几步", f'第{exp["step_no"]}步' if exp.get("step_no") else "—"),
    ]
    if exp["yield_pct"] is not None:
        rows.append(("收率", f'{exp["yield_pct"]}%'))
    if exp["purity_pct"] is not None:
        rows.append(("纯度", f'{exp["purity_pct"]}%'))
    if d["tags"]:
        rows.append(("标签", ", ".join(d["tags"])))
    return rows


# ---------------------------------------------------------------- PDF
def export_experiment_pdf(exp_id: int) -> str:
    """Export one experiment to PDF. Returns the generated file path."""
    from xhtml2pdf import pisa

    d = _load_experiment(exp_id)
    if not d:
        raise ValueError("实验不存在")
    exp = d["exp"]
    fonts = _register_fonts()

    tmpdir = tempfile.mkdtemp(prefix="chemeln_pdf_")
    try:
        # --- 反应方程式（表格布局，避免 flex 在 PDF 中错乱） ---
        rxn_html = ""
        if d["reaction"]:
            rx = d["reaction"]
            if (rx.get("display_mode") or "scheme") == "image" and rx.get("image_path"):
                # 图片模式（ChemDraw / 拍照导入的反应式）：必须内嵌 base64，
                # xhtml2pdf 走的是独立渲染进程，本地 file:// 与站内路径都不可靠。
                uri = attachment_data_uri(rx["image_path"])
                if uri:
                    rxn_html = ('<h2>反应方程式</h2>'
                                f'<p align="center"><img src="{uri}" {_pdf_img_attrs(rx["image_path"])}/></p>')
                else:
                    rxn_html = ('<h2>反应方程式</h2>'
                                '<p>（反应式图片文件缺失，未能在导出中显示）</p>')
            else:
                reactants, products = _reaction_items(rx, tmpdir)

                def side(items):
                    cells = ""
                    for it in items:
                        img = (f'<img src="data:image/png;base64,{it["b64"]}" width="110"/>'
                               if it["b64"] else "")
                        cells += (
                            f'<td align="center" valign="top" style="padding:4px">'
                            f'{img}<div style="font-size:9pt">{it["name"]}</div>'
                            f'<div style="font-size:8pt;color:#64748b">{it["meta"]}</div></td>')
                    return cells

                arrow = rx.get("arrow_label") or ""
                cond = rx.get("conditions") or ""
                rxn_html = (
                    '<h2>反应方程式</h2>'
                    '<table border="0" cellpadding="4" cellspacing="0"><tr>'
                    + side(reactants)
                    + f'<td align="center" valign="middle" style="padding:8px">'
                      f'<div style="font-size:9pt">{arrow}</div>'
                      f'<div style="font-size:18pt">&#10230;</div>'
                      f'<div style="font-size:8pt;color:#64748b">{cond}</div></td>'
                    + side(products)
                    + '</tr></table>')

        # --- 投料表 ---
        reagent_html = ""
        if d["reagents"]:
            rows = "".join(
                f'<tr><td>{i+1}</td><td>{r["name"] or "—"}</td>'
                f'<td>{ROLE_NAMES.get(r["role"], r["role"] or "—")}</td>'
                f'<td>{r["mw"] if r["mw"] is not None else "—"}</td>'
                f'<td>{_ratio_text(r)}</td><td>{_mass_text(r)}</td>'
                f'<td>{_mol_text(r)}</td><td>{_vol_text(r)}</td></tr>'
                for i, r in enumerate(d["reagents"]))
            reagent_html = (
                '<h2>投料表</h2>'
                '<table border="1" cellpadding="5" cellspacing="0" repeat="1">'
                '<thead><tr><th>#</th><th>名称</th><th>角色</th><th>MW</th><th>投料比</th>'
                '<th>投料质量(g)</th><th>摩尔(mmol)</th><th>体积(mL)</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')

        # --- 化合物信息 ---
        compound_html = ""
        if d["compound"]:
            c = d["compound"]
            compound_html = (
                '<h2>化合物信息</h2><ul>'
                f'<li><b>名称：</b>{c["name"]}</li>'
                f'<li><b>CAS：</b>{c["cas"] or "—"}</li>'
                f'<li><b>SMILES：</b>{c["smiles"] or ""}</li>'
                f'<li><b>分子式：</b>{c["formula"] or "—"}</li>'
                f'<li><b>分子量：</b>{c["mw"] or "—"}</li></ul>')

        # --- 附件清单 ---
        attach_html = ""
        if d["attachments"]:
            items = "".join(f'<li>{a["filename"]}</li>' for a in d["attachments"])
            attach_html = f'<h2>附件</h2><ul>{items}</ul>'

        # --- 正文：把附件相对路径改为本地绝对路径，供 PDF 渲染 ---
        content = exp["content"] or "<p>（无内容）</p>"
        content = strip_inline_fonts(content)      # 内联字体声明会顶掉统一字体
        attach_uri = ATTACH_DIR.replace("\\", "/")
        content = content.replace('src="/attachments/', f'src="file:///{attach_uri}/')
        meta_table = "".join(
            f'<tr><th align="left" width="100">{k}</th><td>{v}</td></tr>'
            for k, v in _meta_rows(d))

        html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{exp['title']}</title>
<style>
  {_font_css(fonts)}
  body {{ font-size: 10.5pt; color:#1e293b; line-height:1.6; }}
  h1 {{ font-size:18pt; color:#2c3e50; border-bottom:1px solid #cbd5e1; padding-bottom:6px; }}
  h2 {{ font-size:13pt; color:#2c3e50; border-bottom:1px solid #e2e8f0; padding-bottom:4px; }}
  table {{ border-collapse: collapse; width:100%; margin:10px 0; }}
  th,td {{ border:1px solid #cbd5e1; padding:5px 8px; font-size:9.5pt; }}
  img {{ max-width:100%; }}
  code {{ background:#f1f5f9; padding:1px 4px; }}
</style></head><body>
<h1>{exp['title']}</h1>
<table border="1" cellpadding="4">{meta_table}</table>
{rxn_html}
{reagent_html}
<h2>实验内容</h2>
{content}
{compound_html}
{attach_html}
<hr>
<p style="color:#94a3b8;font-size:9pt">导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""

        # 中文/符号片段套上对应字体的 span（xhtml2pdf 不做逐字符回退）
        html = wrap_font_runs(html, fonts)

        os.makedirs(BACKUP_DIR, exist_ok=True)
        out_path = os.path.join(
            BACKUP_DIR, f"experiment_{exp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        with open(out_path, "wb") as f:
            pisa.CreatePDF(html, dest=f, encoding="utf-8")
        return out_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --------------------------------------------------------------- Word
def _apply_export_fonts(doc):
    """把整篇 Word 统一成「西文 Times New Roman + 中文 宋体」。

    ⛔ 三个坑，少一个就统一不了：
    1) 只改 Normal 样式没用。标题、表格用的是各自的内置样式（Title / Heading N /
       List Bullet …），它们自带 rFonts，会盖掉 Normal；
    2) rFonts 上若同时存在 asciiTheme 与 ascii，Word **优先用主题字体**
       （默认模板里的标题就是 asciiTheme="majorHAnsi"，即等线/Calibri Light），
       所以必须把 theme 系列属性删掉，显式字体才生效；
    3) 中文由 w:eastAsia 决定 —— 只设 style.font.name（= ascii/hAnsi），
       中文仍会用原字体。西文/中文要分别落到 w:ascii|w:hAnsi 与 w:eastAsia。
    """
    try:
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except ImportError:
        return
    theme_attrs = ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme")

    def fix(rPr):
        if rPr is None:
            return False
        rf = rPr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rPr.insert(0, rf)
        for attr in theme_attrs:
            key = qn(attr)
            if rf.get(key) is not None:
                del rf.attrib[key]
        rf.set(qn("w:ascii"), FONT_LATIN)
        rf.set(qn("w:hAnsi"), FONT_LATIN)
        rf.set(qn("w:eastAsia"), FONT_CJK)
        rf.set(qn("w:cs"), FONT_LATIN)
        return True

    styles = doc.styles.element

    # 1) 文档级默认字体（未被样式显式覆盖的文本都落在这里）
    dd = styles.find(qn("w:docDefaults"))
    if dd is None:
        dd = OxmlElement("w:docDefaults")
        styles.insert(0, dd)
    rprd = dd.find(qn("w:rPrDefault"))
    if rprd is None:
        rprd = OxmlElement("w:rPrDefault")
        dd.append(rprd)
    rPr = rprd.find(qn("w:rPr"))
    if rPr is None:
        rPr = OxmlElement("w:rPr")
        rprd.append(rPr)
    fix(rPr)

    # 2) 每个样式定义里的字体（含 Title / Heading 1-9 / List Bullet / Table Grid）
    #    ⛔ 要递归找 rPr：样式里的字体可能挂在 w:pPr/w:rPr 或
    #    w:tblStylePr/w:pPr/w:rPr 下（表格样式就是这样）。只改直接子级会漏掉，
    #    单元格正文就会继续用主题字体（Calibri/等线）。
    for st in styles.findall(qn("w:style")):
        found = list(st.iter(qn("w:rPr")))
        if not found:
            if st.get(qn("w:type")) not in ("paragraph", "character"):
                continue
            st_rPr = OxmlElement("w:rPr")
            st.append(st_rPr)
            found = [st_rPr]
        for st_rPr in found:
            fix(st_rPr)


def _add_inline(paragraph, node):
    """Add runs for inline content (text, bold/italic/underline, images)."""
    from docx.shared import Inches
    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():
                paragraph.add_run(text)
        elif child.name == "img":
            src = child.get("src", "")
            if src.startswith("data:image"):
                try:
                    b64 = src.split(",", 1)[1]
                    tmp = os.path.join(tempfile.mkdtemp(prefix="chemeln_img_"), "img.png")
                    with open(tmp, "wb") as f:
                        f.write(base64.b64decode(b64))
                    paragraph.add_run().add_picture(tmp, width=Inches(2.0))
                except Exception:
                    pass
            elif src.startswith("/attachments/"):
                p = os.path.join(ATTACH_DIR, src[len("/attachments/"):])
                if os.path.exists(p):
                    try:
                        paragraph.add_run().add_picture(p, width=Inches(2.5))
                    except Exception:
                        pass
        elif child.name == "br":
            paragraph.add_run("\n")
        elif child.name in ("b", "strong"):
            r = paragraph.add_run(child.get_text())
            r.bold = True
        elif child.name in ("i", "em"):
            r = paragraph.add_run(child.get_text())
            r.italic = True
        elif child.name == "u":
            r = paragraph.add_run(child.get_text())
            r.underline = True
        elif child.name == "code":
            paragraph.add_run(child.get_text())     # 字体由 _apply_export_fonts 统一
        elif child.name == "a":
            paragraph.add_run(child.get_text())
        elif child.name in ("span", "div", "p", "font", "small", "em"):
            _add_inline(paragraph, child)
        else:
            _add_inline(paragraph, child)


def _add_html_to_docx(doc, html):
    """Convert a subset of HTML (headings/p/lists/table/img/pre/hr) into docx elements."""
    from docx.shared import Inches
    soup = BeautifulSoup(html or "", "html.parser")

    def walk(node):
        for el in list(node.children):
            if isinstance(el, NavigableString):
                text = str(el).strip()
                if text:
                    doc.add_paragraph(text)
                continue
            name = el.name
            if name in ("h1", "h2", "h3", "h4"):
                doc.add_heading(el.get_text(" ", strip=True), level=int(name[1]))
            elif name == "p":
                p = doc.add_paragraph()
                _add_inline(p, el)
            elif name in ("ul", "ol"):
                style = "List Bullet" if name == "ul" else "List Number"
                for li in el.find_all("li", recursive=False):
                    p = doc.add_paragraph(style=style)
                    _add_inline(p, li)
            elif name == "table":
                rows = el.find_all("tr")
                if not rows:
                    continue
                ncol = max(len(r.find_all(["td", "th"])) for r in rows)
                tbl = doc.add_table(rows=0, cols=max(ncol, 1))
                tbl.style = "Table Grid"
                for r in rows:
                    cells = r.find_all(["td", "th"])
                    row = tbl.add_row()
                    for i in range(ncol):
                        text = cells[i].get_text(" ", strip=True) if i < len(cells) else ""
                        row.cells[i].text = text
            elif name == "img":
                src = el.get("src", "")
                try:
                    if src.startswith("data:image"):
                        tmp = os.path.join(tempfile.mkdtemp(prefix="chemeln_img_"), "img.png")
                        with open(tmp, "wb") as f:
                            f.write(base64.b64decode(src.split(",", 1)[1]))
                        doc.add_picture(tmp, width=Inches(3.0))
                    elif src.startswith("/attachments/"):
                        p = os.path.join(ATTACH_DIR, src[len("/attachments/"):])
                        if os.path.exists(p):
                            doc.add_picture(p, width=Inches(4.0))
                except Exception:
                    pass
            elif name == "pre":
                doc.add_paragraph(el.get_text())    # 字体由 _apply_export_fonts 统一
            elif name == "blockquote":
                p = doc.add_paragraph(el.get_text(" ", strip=True))
                p.paragraph_format.left_indent = Inches(0.3)
            elif name == "hr":
                doc.add_paragraph("─" * 40)
            elif name in ("div", "section", "article", "figure", "tbody", "thead", "span"):
                walk(el)
            else:
                walk(el)

    walk(soup)


def export_experiment_docx(exp_id: int) -> str:
    """Export one experiment to a Word (.docx) file. Returns the file path."""
    from docx import Document
    from docx.shared import Inches

    d = _load_experiment(exp_id)
    if not d:
        raise ValueError("实验不存在")
    exp = d["exp"]

    doc = Document()
    _apply_export_fonts(doc)
    doc.add_heading(exp["title"], level=0)

    # 元信息
    for k, v in _meta_rows(d):
        p = doc.add_paragraph()
        r = p.add_run(f"{k}：")
        r.bold = True
        p.add_run(str(v))

    # 反应方程式
    tmpdir = tempfile.mkdtemp(prefix="chemeln_docx_")
    try:
        if d["reaction"]:
            doc.add_heading("反应方程式", level=1)
            rx = d["reaction"]
            img_full = (attachment_abs_path(rx.get("image_path"))
                        if (rx.get("display_mode") or "scheme") == "image" else "")
            if img_full:
                # 图片模式（ChemDraw / 拍照导入）：整图居中插入。
                # 宽度按原图 96dpi 折算，最多占满可用页宽（A4 去默认页边距约 6.2in）。
                from docx.enum.text import WD_ALIGN_PARAGRAPH
                width_in = 5.5
                try:
                    from PIL import Image
                    with Image.open(img_full) as im:
                        width_in = min(5.5, max(1.0, im.width / 96.0))
                except Exception:
                    pass
                doc.add_picture(img_full, width=Inches(width_in))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                reactants, products = _reaction_items(rx, tmpdir)
                ncol = max(len(reactants), 1) + 1 + max(len(products), 1)
                tbl = doc.add_table(rows=1, cols=ncol)
                tbl.style = "Table Grid"
                cells = tbl.rows[0].cells
                ci = 0
                for it in reactants:
                    c = cells[ci]
                    if it["path"]:
                        try:
                            c.paragraphs[0].add_run().add_picture(it["path"], width=Inches(1.1))
                        except Exception:
                            pass
                    c.add_paragraph(it["name"])
                    if it["meta"]:
                        c.add_paragraph(it["meta"])
                    ci += 1
                mid = cells[ci]
                mid.paragraphs[0].add_run(rx.get("arrow_label") or "").bold = True
                mid.add_paragraph("⟶")
                if rx.get("conditions"):
                    mid.add_paragraph(rx["conditions"])
                ci += 1
                for it in products:
                    c = cells[ci]
                    if it["path"]:
                        try:
                            c.paragraphs[0].add_run().add_picture(it["path"], width=Inches(1.1))
                        except Exception:
                            pass
                    c.add_paragraph(it["name"])
                    if it["meta"]:
                        c.add_paragraph(it["meta"])
                    ci += 1

        # 投料表
        if d["reagents"]:
            doc.add_heading("投料表", level=1)
            headers = ["#", "名称", "角色", "MW", "投料比", "投料质量(g)", "摩尔(mmol)", "体积(mL)"]
            tbl = doc.add_table(rows=1, cols=len(headers))
            tbl.style = "Table Grid"
            for i, h in enumerate(headers):
                cell = tbl.rows[0].cells[i]
                cell.text = h
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.bold = True
            for i, r in enumerate(d["reagents"]):
                row = tbl.add_row()
                vals = [str(i + 1), r["name"] or "—",
                        ROLE_NAMES.get(r["role"], r["role"] or "—"),
                        str(r["mw"] if r["mw"] is not None else "—"),
                        _ratio_text(r), str(_mass_text(r)),
                        str(_mol_text(r)), str(_vol_text(r))]
                for j, v in enumerate(vals):
                    row.cells[j].text = v

        # 正文
        doc.add_heading("实验内容", level=1)
        _add_html_to_docx(doc, exp["content"] or "<p>（无内容）</p>")

        # 化合物信息
        if d["compound"]:
            c = d["compound"]
            doc.add_heading("化合物信息", level=1)
            for k, v in [("名称", c["name"]), ("CAS", c["cas"] or "—"),
                         ("SMILES", c["smiles"] or ""),
                         ("分子式", c["formula"] or "—"), ("分子量", c["mw"] or "—")]:
                p = doc.add_paragraph()
                p.add_run(f"{k}：").bold = True
                p.add_run(str(v))

        # 附件
        if d["attachments"]:
            doc.add_heading("附件", level=1)
            for a in d["attachments"]:
                doc.add_paragraph(f'{a["filename"]} ({a["file_type"]})', style="List Bullet")

        doc.add_paragraph()
        p = doc.add_paragraph(f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        p.runs[0].font.size = None

        os.makedirs(BACKUP_DIR, exist_ok=True)
        out_path = os.path.join(
            BACKUP_DIR, f"experiment_{exp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx")
        doc.save(out_path)
        return out_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
