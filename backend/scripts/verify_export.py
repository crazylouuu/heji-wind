# -*- coding: utf-8 -*-
"""导出格式验证（在数据库临时副本上跑，真实数据零改动）。

断言四件事：
  1. 图片模式（display_mode=image）的反应式在 HTML / PDF / Word 中都能出现
     —— 之前 Word/PDF 只处理 SMILES 模式，图片模式整段丢失；
     HTML 则写的是站内路径 /attachments/xxx，下载到本地后必然裂图。
  2. 反应方程式 + 投料表排在「实验内容」之前。
  3. 正文里插入的附件图片被内嵌（data URI），不再依赖服务器。
  4. 三种导出的字体统一为「西文 Times New Roman + 中文 宋体」：
     PDF 实际绘字必须落在 TimesNewRoman / SimSun 上，且不能出现空字形（\\x00）。
  5. 投料表「投料质量(g) / 摩尔(mmol) / 体积(mL)」的显示位数规则：
     <0 → 3 位小数，0 ≤ v < 10 → 2 位，v ≥ 10 → 1 位；
     MD / HTML / PDF / Word 输出格式化文本，Excel 保留数值 + 条件数字格式，
     且前端 format.js 与后端 fmt_quantity() 结果必须逐值一致。
  6. 误抄的免责声明「仅供参考，非投资建议」不得再出现在任何导出与页面里。
  7. 版本号四处一致，且 CHANGELOG.md 里有当前版本的说明小节。

用法:
    python backend/scripts/verify_export.py            # 默认验证实验 20 / 21
    python backend/scripts/verify_export.py 20 21      # 指定实验 id
"""
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from decimal import Decimal, ROUND_HALF_UP

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

from utils import export as ex                 # noqa: E402
from utils import export_formats as exf        # noqa: E402

REAL_DB = ex.DB_PATH
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def api_layer(exp_ids, tmp_db):
    """走真实 HTTP 路由（TestClient，进程内）再验一遍。

    为什么要有这一层：格式层直接调函数，只能证明「函数对」；真正决定用户看到
    什么的是路由。曾出现「函数已修好、端口上跑的却是旧进程」导致的误判，
    所以这里连 /api/health 的版本与代码指纹一起断言。
    """
    print("--- API 层（真实路由，TestClient，不监听端口）---")
    import database
    database.DB_PATH = tmp_db
    ex.DB_PATH = exf.DB_PATH = tmp_db

    from fastapi.testclient import TestClient
    from utils.code_fingerprint import compute
    import main as M  # noqa: N812

    # ⛔ 不写成 `with TestClient(...)`：那样会触发 lifespan（init_db + 自动备份
    #    线程）。不用上下文管理器则只发请求，不碰真实数据库与服务状态。
    client = TestClient(M.app)

    r = client.get("/api/health")
    info = r.json() if r.status_code == 200 else {}
    check("GET /api/health 返回 200", r.status_code == 200, str(info))
    check("/api/health 带应用版本", bool(info.get("version")), str(info.get("version")))
    local_fp = compute()
    check("/api/health 的代码指纹与本地一致",
          info.get("code_fingerprint") == local_fp,
          f"{info.get('code_fingerprint')} vs {local_fp}")

    db = sqlite3.connect(tmp_db)
    db.row_factory = sqlite3.Row
    for eid in exp_ids:
        row = db.execute("SELECT id,title FROM experiments WHERE id=?", (eid,)).fetchone()
        if not row:
            continue
        rx = db.execute("SELECT display_mode FROM reactions WHERE experiment_id=? LIMIT 1",
                        (eid,)).fetchone()
        mode = (rx["display_mode"] if rx else None) or "-"

        r = client.get(f"/api/data/export/experiment/{eid}/html")
        check(f"路由 HTML 导出 200（实验 {eid}）", r.status_code == 200, f"{len(r.text)} B")
        if mode == "image":
            check(f"路由 HTML 内嵌反应式图（实验 {eid}）",
                  "data:image/png;base64," in r.text and "/attachments/" not in r.text,
                  f"attachments 残留={r.text.count('/attachments/')}")

        r = client.get(f"/api/data/export/experiment/{eid}/docx")
        check(f"路由 Word 导出 200（实验 {eid}）", r.status_code == 200,
              f"{len(r.content)} B")
        if r.status_code == 200:
            blob = r.content
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                media = [n for n in z.namelist() if n.startswith("word/media/")]
            check(f"路由 Word 含图片（实验 {eid}）", len(media) >= 1, f"{len(media)} 个")

        r = client.get(f"/api/data/export/experiment/{eid}/pdf")
        check(f"路由 PDF 导出 200（实验 {eid}）", r.status_code == 200,
              f"{len(r.content)} B")
        if r.status_code == 200 and mode == "image":
            n_img = (r.content.count(b"/Subtype /Image")
                     + r.content.count(b"/Subtype/Image"))
            check(f"路由 PDF 内嵌反应式图（实验 {eid}）", n_img >= 1, f"{n_img} 个")
    db.close()
    print()


def unit_checks():
    """纯函数的小用例（不依赖数据库）。"""
    print("--- 工具函数 ---")
    got = ex.strip_inline_fonts('<p style="font-family:楷体;color:red">x</p>')
    check("strip_inline_fonts 只清字体、保留其它样式",
          got == '<p style="color:red">x</p>', got)
    got = ex.strip_inline_fonts('<font face="黑体" color="red">x</font>')
    check("strip_inline_fonts 清理 <font face>", got == '<font color="red">x</font>', got)

    # 投料质量 / 摩尔数的显示位数规则（写死的期望值，独立于实现）
    qty_cases = [
        (12.3456, "12.3"),      # ≥10 → 1 位
        (10, "10.0"),           # 边界：正好 10 → 1 位
        (9.999, "10.00"),       # 边界：按原值判定（9.999 < 10）→ 2 位
        (5.3792, "5.38"),       # 0~10 → 2 位
        (0.5237, "0.52"),
        (0, "0.00"),
        (2.675, "2.68"),        # 十进制半进位（不是 2.67）
        (-0.1234, "-0.123"),    # <0 → 3 位
        (-50.5678, "-50.568"),  # <0 一律 3 位（不随量级变化）
        (284.5578, "284.6"),
        (None, None),
    ]
    bad = [(v, ex.fmt_quantity(v), want) for v, want in qty_cases
           if ex.fmt_quantity(v) != want]
    check("fmt_quantity 显示规则（11 个用例）", not bad, str(bad))
    check("QTY_EXCEL_FORMAT 三档条件格式",
          ex.QTY_EXCEL_FORMAT == "[<0]0.000;[>=10]0.0;0.00", ex.QTY_EXCEL_FORMAT)
    check("Excel 数字格式覆盖质量/摩尔/体积三列（F~H）",
          ex.QTY_EXCEL_COLS == (6, 8), str(ex.QTY_EXCEL_COLS))

    # 体积(mL) 与质量/摩尔同规则（Word / PDF 的文本层实现）
    vol_cases = [
        ({"ratio_type": "equiv", "volume_ml": 12.3456}, "12.3"),    # ≥10 → 1 位
        ({"ratio_type": "equiv", "volume_ml": 5.3792}, "5.38"),     # 0~10 → 2 位
        ({"ratio_type": "equiv", "volume_ml": -0.5678}, "-0.568"),  # <0 → 3 位
        ({"ratio_type": "weight", "volume_ml": 12.3456}, "—"),      # 重量比不算体积
        ({"ratio_type": "equiv", "volume_ml": None}, "—"),
    ]
    bvol = [(c["volume_ml"], exf._vol_text(c), w) for c, w in vol_cases
            if exf._vol_text(c) != w]
    check("体积(mL) 与质量/摩尔同规则（5 个用例）", not bvol, str(bvol))

    js_parity_check()

    fonts = exf._register_fonts()
    check("字体注册: 西文 Times New Roman",
          fonts["latin"].startswith("Times"), str(fonts["latin"]))
    check("字体注册: 中文宋体", fonts["cjk"] in ("SimSun", "STSong-Light"),
          str(fonts["cjk"]))
    wrapped = exf.wrap_font_runs("<p>AB 中文 &#10230; ①</p>", fonts)
    check("中文被包进宋体 span", 'class="f-cjk">中文' in wrapped, wrapped)
    check("字符引用还原后走符号字体（&#10230; → f-sym）",
          'class="f-sym">\u27f6' in wrapped, wrapped)
    check("西文不加 span（默认即 Times）", "<p>AB " in wrapped, wrapped)
    print()


def font_layer(eid, html, docx, blob):
    """三种导出格式的字体一致性断言。"""
    # ---- HTML ----
    decls = re.findall(r"font-family\s*:\s*([^;}]*)", html)
    check(f"HTML 字体声明唯一（实验 {eid}）", len(set(decls)) == 1, str(set(decls)))
    check(f"HTML 字体链含 Times New Roman + 宋体（实验 {eid}）",
          "Times New Roman" in html and "宋体" in html)
    check(f"HTML 正文无内联 font-family 残留（实验 {eid}）",
          not re.search(r'style="[^"]*font-family', html, re.I))

    # ---- Word ----
    with zipfile.ZipFile(docx) as z:
        styles = z.read("word/styles.xml").decode("utf-8", "replace")
    check(f"Word 西文字体 = Times New Roman（实验 {eid}）",
          'w:ascii="Times New Roman"' in styles and 'w:hAnsi="Times New Roman"' in styles)
    check(f"Word 中文字体 = 宋体（实验 {eid}）", 'w:eastAsia="宋体"' in styles)
    # theme 字体优先级高于显式字体，留一个就等于没改
    check(f"Word 无主题字体残留（实验 {eid}）",
          not re.search(r'w:(asciiTheme|hAnsiTheme|eastAsiaTheme|cstheme)=', styles),
          f"{len(re.findall('asciiTheme', styles))} 处")

    # ---- PDF ----
    try:
        from pypdf import PdfReader
    except ImportError:
        print("   [SKIP] 未安装 pypdf，跳过 PDF 字体断言")
        return
    reader = PdfReader(io.BytesIO(blob))
    used = set()
    for page in reader.pages:
        def visitor(text, cm, tm, font_dict, font_size, _s=used):
            if text and text.strip():
                _s.add(str(font_dict.get("/BaseFont", "")))
        page.extract_text(visitor_text=visitor)
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    check(f"PDF 西文实际绘字用 Times New Roman（实验 {eid}）",
          any("TimesNewRoman" in b or "Times-Roman" in b for b in used),
          ", ".join(sorted(used)))
    check(f"PDF 中文实际绘字用宋体（实验 {eid}）",
          any("SimSun" in b or "STSong" in b for b in used),
          ", ".join(sorted(b for b in used if "Times" not in b)))
    # 字体缺字时 PDF 会写出空字形，提取出来就是 \x00
    check(f"PDF 无空字形（实验 {eid}）", "\x00" not in text,
          f"{text.count(chr(0))} 个")
    print()


def _find_node():
    node = shutil.which("node")
    if node:
        return node
    # 本机 Bash PATH 受损时 which 可能找不到，退回 WorkBuddy 托管版本
    cand = os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node",
                        "versions", "22.22.2-3", "node.exe")
    return cand if os.path.exists(cand) else None


def js_parity_check():
    """前端 Fmt.qty 与后端 fmt_quantity 必须逐值一致。

    前后端各写一份格式化逻辑（浏览器里没有 Python），一旦两边漂移，
    用户就会看到「页面上是 5.38、导出里是 5.4」这种鬼故事，所以直接跑真 JS 比对。
    """
    node = _find_node()
    fmt_js = os.path.join(os.path.dirname(BACKEND), "frontend", "js", "format.js")
    if not node or not os.path.exists(fmt_js):
        print(f"   [SKIP] 无法跑前端一致性断言（node={node} js={os.path.exists(fmt_js)}）")
        return
    vals = [0, 0.5237, 5.3792, 9.999, 10, 12.3456, 85.3673, 284.5578,
            2.675, 0.125, -0.1234, -50.5678, 1000]
    harness = (
        "const F = require(process.argv[2]);\n"
        "const vals = JSON.parse(process.argv[3]);\n"
        "process.stdout.write(JSON.stringify(vals.map(v => F.qty(v))));\n"
    )
    tmp = tempfile.mkdtemp(prefix="chemeln_qty_")
    try:
        hpath = os.path.join(tmp, "harness.js")
        with open(hpath, "w", encoding="utf-8") as f:
            f.write(harness)
        p = subprocess.run([node, hpath, fmt_js, json.dumps(vals)],
                           capture_output=True, text=True, encoding="utf-8")
        if p.returncode != 0:
            check("前端 format.js 可被 node 加载", False, (p.stderr or "")[-300:])
            return
        js_out = json.loads(p.stdout)
    except Exception as e:                      # noqa: BLE001
        check("前端 format.js 一致性断言可执行", False, f"{type(e).__name__}: {e}")
        return
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    py_out = [ex.fmt_quantity(v) for v in vals]
    diff = [(v, a, b) for v, a, b in zip(vals, py_out, js_out) if a != b]
    check(f"前后端显示规则一致（{len(vals)} 个用例）", not diff, str(diff))


def expected_qty(value):
    """测试侧独立实现的显示规则（故意不复用被测函数，避免自证）。"""
    d = Decimal(str(value))
    n = 3 if d < 0 else (2 if d < 10 else 1)
    return f"{d.quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP):f}"


def _expect_rows(conn, eid):
    """从库里取投料表，算出一行行「应该显示成什么」，供各格式比对。"""
    rows = conn.execute("SELECT * FROM reagents WHERE experiment_id=? ORDER BY sort_order",
                        (eid,)).fetchall()
    out = []
    for r in rows:
        mass = r["mass_g"]
        if mass is None and r["mass_mg"] is not None:
            mass = r["mass_mg"] / 1000.0
        mol = None if r["ratio_type"] == "weight" else r["moles_mmol"]
        vol = None if r["ratio_type"] == "weight" else r["volume_ml"]
        out.append({
            "name": r["name"],
            "mass": None if mass is None else expected_qty(mass),
            "mol": None if mol is None else expected_qty(mol),
            "vol": None if vol is None else expected_qty(vol),
            "mass_raw": None if mass is None else str(float(mass)),
            "mol_raw": None if mol is None else str(float(mol)),
            "vol_raw": None if vol is None else str(float(vol)),
        })
    return out


QTY_LABELS = (("mass", "投料质量"), ("mol", "摩尔"), ("vol", "体积"))


def quantity_layer(eid, expects, html, docx_text, pdf_text, xlsx):
    """投料质量 / 摩尔 / 体积 的显示位数在四种导出里是否都落地。"""
    hits = [e for e in expects if any(e[k] for k, _ in QTY_LABELS)]
    if not hits:
        print("   [SKIP] 该实验没有投料表数值数据")
        return

    # 覆盖度：避免"某列一个数都没有"时检查静默空转通过
    cov = {k: sum(1 for e in expects if e[k]) for k, _ in QTY_LABELS}
    note = ""
    if not cov["vol"]:
        note = "  ← 该实验无体积数据，体积规则由后面的合成用例覆盖"
    print(f"   覆盖度: 质量 {cov['mass']} 行 / 摩尔 {cov['mol']} 行 / 体积 {cov['vol']} 行{note}")

    def missing(container, kind, cells=False):
        gone = []
        for e in expects:
            v = e[kind]
            if not v:
                continue
            found = f">{v}<" in container if cells else v in container
            if not found:
                gone.append(f'{e["name"]}={v}')
        return gone

    for kind, label in QTY_LABELS:
        name = f'{label}({"g" if kind == "mass" else "mmol" if kind == "mol" else "mL"})'
        check(f"HTML {name}已格式化（实验 {eid}）", not missing(html, kind, True),
              ", ".join(missing(html, kind, True)))
    check(f"Word 投料质量/摩尔/体积已格式化（实验 {eid}）",
          not any(missing(docx_text, k) for k, _ in QTY_LABELS),
          ", ".join(sum((missing(docx_text, k) for k, _ in QTY_LABELS), [])))
    check(f"PDF 投料质量/摩尔/体积已格式化（实验 {eid}）",
          not any(missing(pdf_text, k) for k, _ in QTY_LABELS),
          ", ".join(sum((missing(pdf_text, k) for k, _ in QTY_LABELS), [])))

    # 负向：未格式化的原始精度不该再出现在导出里
    leftovers = []
    for e in expects:
        for kind, _ in QTY_LABELS:
            raw, fmt = e[f"{kind}_raw"], e[kind]
            if raw and fmt and raw != fmt and raw in html:
                leftovers.append(f'{e["name"]}:{raw}')
    check(f"HTML 不再出现未格式化的原始精度（实验 {eid}）", not leftovers,
          ", ".join(leftovers))

    # Excel：值仍是数字（可求和），只是数字格式变了
    from openpyxl import load_workbook
    wb = load_workbook(xlsx)
    ws = wb["投料表"]
    fmts, numeric = set(), 0
    for row in ws.iter_rows(min_row=2, min_col=ex.QTY_EXCEL_COLS[0],
                            max_col=ex.QTY_EXCEL_COLS[1]):
        for cell in row:
            if isinstance(cell.value, (int, float)):
                numeric += 1
                fmts.add(cell.number_format)
    check("Excel 投料质量/摩尔/体积列保留数值（可再计算）", numeric >= 2,
          f"{numeric} 个数值单元格")
    check("Excel 投料质量/摩尔/体积列用条件数字格式",
          fmts == {ex.QTY_EXCEL_FORMAT}, str(fmts) or "无")
    print()


SYNTH_TITLE = "【验证用】数值格式（临时库，不会进真实数据）"


def synthetic_layer(conn):
    """造一条已知数值的投料表，真正验证三档规则在四种导出里落地。

    为什么需要它：真实实验往往没有体积数据（没填密度/浓度就不会算体积），
    若只拿真实数据断言，"体积已格式化"这类检查会**空转通过**——
    看起来 PASS，其实一个数都没验。这里用一组能覆盖三档边界的数值补上。
    """
    print("--- 合成用例：三档数值在四种导出中是否真的格式化 ---")
    cur = conn.execute(
        "INSERT INTO experiments (title, content, project, status, exp_date) VALUES (?,?,?,?,?)",
        (SYNTH_TITLE, "<p>正文</p>", "验证", "draft", "2026-09-19"))
    eid = cur.lastrowid
    # role, name, mw, ratio_type, ratio_value, mass_g, moles_mmol, volume_ml
    rows = [
        ("substrate", "验证-常规", 140.569, "equiv", None, 5.3792, 38.2666, 4.5237),
        ("reagent", "验证-微量", 63.012, "equiv", 1.2, 0.1234, 1.2345, 0.5678),
        ("reagent", "验证-大批量", 100.205, "equiv", 4.0, 10.0, 71.1394, 30.04),
        ("reagent", "验证-负值", 50.0, "weight", 2.0, -0.1234, 2.5, 3.5),
    ]
    for i, (role, name, mw, rt, rv, mass, mol, vol) in enumerate(rows):
        conn.execute(
            "INSERT INTO reagents (experiment_id, role, name, mw, ratio_type, ratio_value,"
            " mass_g, moles_mmol, volume_ml, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (eid, role, name, mw, rt, rv, mass, mol, vol, i))
    conn.commit()

    try:
        # 期望值用测试侧独立实现算，且逐条列出「原值 → 应显示成什么」
        want, raw = [], set()
        for role, name, _mw, rt, _rv, mass, mol, vol in rows:
            for kind, v in (("mass", mass), ("mol", mol), ("vol", vol)):
                if rt == "weight" and kind in ("mol", "vol"):
                    continue                      # 重量比模式不显示摩尔/体积
                shown = expected_qty(v)
                want.append((f"{name}.{kind}", shown))
                # 只有「显示值 != 原值」时，原值才算不该出现的残留
                # （如 10.0 本来就显示成 "10.0"，不能反过来当成泄露）
                if str(float(v)) != shown:
                    raw.add(str(float(v)))

        def absent(container, cells=False):
            return [f"{n}={v}" for n, v in want
                    if (f">{v}<" if cells else v) not in container]

        html = ex.export_experiment_html(eid)
        md = ex.export_experiment_markdown(eid)

        check("合成 HTML 投料表三档数值命中", not absent(html, True),
              ", ".join(absent(html, True)))
        check("合成 Markdown 投料表三档数值命中", not absent(md),
              ", ".join(absent(md)))
        check("合成 HTML 不再出现原始精度",
              not [r for r in raw if r in html], str([r for r in raw if r in html]))

        pdf = exf.export_experiment_pdf(eid)
        with open(pdf, "rb") as f:
            blob = f.read()
        pdf_flat = _pdf_text(blob)
        check("合成 PDF 投料表三档数值命中", not absent(pdf_flat),
              ", ".join(absent(pdf_flat)))

        docx = exf.export_experiment_docx(eid)
        with zipfile.ZipFile(docx) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        dtext = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))
        check("合成 Word 投料表三档数值命中", not absent(dtext),
              ", ".join(absent(dtext)))

        # Excel：值仍是原始数字（可再计算），格式是条件数字格式
        from openpyxl import load_workbook
        ws = load_workbook(ex.export_experiments_excel([eid]))["投料表"]
        vals, fmts = [], set()
        for row in ws.iter_rows(min_row=2):
            if row[0].value != eid:
                continue
            for cell in row[ex.QTY_EXCEL_COLS[0] - 1:ex.QTY_EXCEL_COLS[1]]:
                if isinstance(cell.value, (int, float)):
                    vals.append(cell.value)
                    fmts.add(cell.number_format)
        check("合成 Excel 保留原始精度数值（5.3792 等）",
              all(any(abs(v - x) < 1e-9 for v in vals) for x in (5.3792, 0.1234, 4.5237)),
              str(vals))
        check("合成 Excel 三列均为条件数字格式",
              fmts == {ex.QTY_EXCEL_FORMAT}, str(fmts) or "无")
    finally:
        conn.execute("DELETE FROM reagents WHERE experiment_id=?", (eid,))
        conn.execute("DELETE FROM experiments WHERE id=?", (eid,))
        conn.commit()
    print()


def _pdf_text(blob):
    """PDF 全部文本（去掉空白，便于子串比对）。"""
    try:
        from pypdf import PdfReader
        return re.sub(r"\s+", "", "\n".join(
            (p.extract_text() or "") for p in PdfReader(io.BytesIO(blob)).pages))
    except ImportError:
        return ""


# 从其它项目误抄进 ELN 的文案，任何导出/页面里都不该再出现
BANNED_PHRASES = ("仅供参考", "非投资建议")


def disclaimer_layer(eid, html, md, docx_text, pdf_text):
    """负向断言：误抄的免责声明已彻底清掉（本 ELN 不是投资类产品）。"""
    places = {"HTML": html, "Markdown": md, "Word": docx_text, "PDF": pdf_text}
    for label, blob in places.items():
        hits = [p for p in BANNED_PHRASES if p in (blob or "")]
        check(f"{label} 无「仅供参考/非投资建议」残留（实验 {eid}）", not hits, str(hits))
    # 页脚时间戳要在（说明删的是那句话，不是整段页脚）
    check(f"HTML 导出时间戳仍在（实验 {eid}）", "导出时间" in html, "")
    check(f"Markdown 导出时间戳仍在（实验 {eid}）", "导出时间" in md, "")


def version_layer():
    """版本号与 CHANGELOG.md 的一致性（与发布门禁同款断言）。"""
    print("--- 版本号与版本说明 ---")
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import check_version
    ver = check_version.app_version()
    problems = check_version.verify(ver)
    check(f"版本号四处一致且 CHANGELOG 有 v{ver} 说明", not problems, str(problems))

    index = open(os.path.join(ROOT, "frontend", "index.html"),
                 encoding="utf-8", errors="replace").read()
    hits = [p for p in BANNED_PHRASES if p in index]
    check("应用页面侧边栏无免责声明残留", not hits, str(hits))
    print()


def main(exp_ids):
    tmp = tempfile.mkdtemp(prefix="chemeln_verify_")
    tmp_db = os.path.join(tmp, "chemeln.db")
    tmp_out = os.path.join(tmp, "out")
    os.makedirs(tmp_out, exist_ok=True)

    # 用 sqlite backup API 复制（服务正在跑，直接拷文件可能拿到不一致的库）
    src = sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp_db)
    src.backup(dst)
    src.close()
    dst.close()

    # 改写模块级路径 → 导出产物落临时目录，DB 用副本
    ex.DB_PATH = exf.DB_PATH = tmp_db
    ex.BACKUP_DIR = exf.BACKUP_DIR = tmp_out

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    print(f"临时库: {tmp_db}\n")

    try:
        unit_checks()
        img_mode_ids = []
        for eid in exp_ids:
            row = conn.execute("SELECT id,title FROM experiments WHERE id=?", (eid,)).fetchone()
            if not row:
                print(f"--- 实验 {eid}: 不存在，跳过 ---\n")
                continue
            rxn = conn.execute("SELECT * FROM reactions WHERE experiment_id=? LIMIT 1",
                               (eid,)).fetchone()
            mode = (rxn["display_mode"] if rxn else None) or "-"
            if mode == "image":
                img_mode_ids.append(eid)
            print(f"--- 实验 {eid} 《{row['title']}》 display_mode={mode} ---")

            # ---------------- HTML ----------------
            html = ex.export_experiment_html(eid)
            has_rxn_h2 = "反应方程式" in html
            i_rxn = html.find("反应方程式")
            i_rg = html.find("投料表")
            i_content = html.find("<h2>实验内容</h2>")
            check("HTML 顺序: 反应方程式 → 投料表 → 实验内容",
                  -1 < i_rxn < i_rg < i_content,
                  f"rxn={i_rxn} reagent={i_rg} content={i_content}")
            if mode == "image":
                check("HTML 反应式图片已内嵌 data URI",
                      "data:image/" in html and "/attachments/" not in html,
                      f"attachments 残留={html.count('/attachments/')}")

            # ---------------- PDF ----------------
            pdf = exf.export_experiment_pdf(eid)
            size = os.path.getsize(pdf)
            check("PDF 生成成功且非空", size > 4000, f"{size} B")
            with open(pdf, "rb") as f:
                blob = f.read()
            n_img = blob.count(b"/Subtype /Image") + blob.count(b"/Subtype/Image")
            if mode == "image":
                check("PDF 内嵌反应式图片（/Image XObject）", n_img >= 1, f"{n_img} 个")
            else:
                check("PDF 含结构式图片", n_img >= 1, f"{n_img} 个")

            # ---------------- Word ----------------
            docx = exf.export_experiment_docx(eid)
            check("Word 生成成功且非空", os.path.getsize(docx) > 4000,
                  f"{os.path.getsize(docx)} B")
            with zipfile.ZipFile(docx) as z:
                media = [n for n in z.namelist() if n.startswith("word/media/")]
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))
            j_rxn = text.find("反应方程式")
            j_rg = text.find("投料表")
            j_content = text.find("实验内容")
            check("Word 顺序: 反应方程式 → 投料表 → 实验内容",
                  -1 < j_rxn < j_rg < j_content,
                  f"rxn={j_rxn} reagent={j_rg} content={j_content}")
            if mode == "image":
                check("Word 含反应式图片（word/media）", len(media) >= 1,
                      f"{len(media)} 个: {[os.path.basename(m) for m in media][:4]}")
            else:
                check("Word 含结构式图片（word/media）", len(media) >= 2,
                      f"{len(media)} 个")

            # ---------------- 字体（三格式统一 Times New Roman + 宋体）----------------
            font_layer(eid, html, docx, blob)

            # ---------------- 投料质量 / 摩尔 / 体积 显示位数 ----------------
            pdf_flat = _pdf_text(blob)
            xlsx = ex.export_experiments_excel([eid])
            quantity_layer(eid, _expect_rows(conn, eid), html, text, pdf_flat, xlsx)

            # ---------------- 免责声明清理（负向）----------------
            disclaimer_layer(eid, html, ex.export_experiment_markdown(eid), text, pdf_flat)
            print(f"   产物: {os.path.basename(pdf)} / {os.path.basename(docx)}")
            print()

        # 合成用例：真实数据可能没有体积，用已知数值确认真落地（防止空转通过）
        synthetic_layer(conn)

        # 负向检查：图片模式实验的 HTML 里不该残留站内图片路径
        for eid in img_mode_ids:
            h = ex.export_experiment_html(eid)
            check(f"HTML 不残留站内图片路径（实验 {eid}）",
                  "/attachments/" not in h,
                  f"残留 {h.count('/attachments/')} 处")
        print()

        api_layer(exp_ids, tmp_db)
        version_layer()
    finally:
        conn.close()
        shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 56)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    for f in FAIL:
        print(f"   ! {f}")
    print("=" * 56)
    return 1 if FAIL else 0


if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]] or [20, 21]
    sys.exit(main(ids))
