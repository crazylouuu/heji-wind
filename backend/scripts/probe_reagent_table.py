# -*- coding: utf-8 -*-
"""临时探针：给「投料表」页签拍张图，肉眼确认显示位数规则真的生效。

⛔ 这个脚本只在开发时用，不参与发布（make_release 的 ROOT_FILES 是白名单）。
安全策略：
  · 数据库用**临时副本**（sqlite backup API），真实 data/chemeln.db 只读；
  · 自动备份线程被替换成 no-op（不往 data/backups 写东西、不触发轮转删除）；
  · 只监听 127.0.0.1:8799，进程随脚本退出而结束；
  · frontend/__probe.html 用完即删。

用法: python backend/scripts/probe_reagent_table.py [实验id]
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PORT = 8799
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

PROBE_JS = """
<script>
(() => {
  const tab = (location.hash || '#reagents').slice(1);
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
  (async () => {
    for (let i = 0; i < 80 && typeof App === 'undefined'; i++) await wait(50);
    // 等 App.init() 自己跳完仪表盘，再切到实验详情（否则会被 init 覆盖回去）
    await wait(2000);
    for (let i = 0; i < 8; i++) {
      await App.openExperiment(EXP_ID);
      await wait(700);
      if (document.querySelector('.exp-detail') && document.querySelector('.tab')) break;
    }
    await wait(500);
    const el = document.querySelector('.tab[data-tab="' + tab + '"]');
    if (el) el.click();
    await wait(1500);
    document.body.setAttribute('data-probe-ready', '1');
  })();
})();
</script>
"""


def find_edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def wait_ready(timeout=30):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with opener.open(f"http://127.0.0.1:{PORT}/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:                       # noqa: BLE001
            time.sleep(0.3)
    return False


def inject_demo_volumes(tmp_db):
    """demo 模式：给临时副本里的投料表补上体积数据。

    真实实验大多没填密度/浓度，于是体积列是空的 —— 想用截图说明
    「体积(mL) 也会按同一规则显示位数」，就得先有数。**只改临时副本**。
    """
    c = sqlite3.connect(tmp_db)
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT id, role, ratio_type, mass_g, mass_mg FROM reagents "
                     "ORDER BY experiment_id, sort_order").fetchall()
    for r in rows:
        if r["ratio_type"] == "weight":
            continue
        mass = r["mass_g"] or (r["mass_mg"] / 1000.0 if r["mass_mg"] else None)
        if not mass:
            continue
        # 用一个"看起来合理"的密度换算出体积，范围天然覆盖两档显示
        c.execute("UPDATE reagents SET volume_ml=? WHERE id=?",
                  (round(mass / 1.1, 4), r["id"]))
    c.commit()
    n = c.execute("SELECT COUNT(*) FROM reagents WHERE volume_ml IS NOT NULL").fetchone()[0]
    c.close()
    return n


def main(exp_id, demo=False):
    tmp = tempfile.mkdtemp(prefix="chemeln_probe_")
    import database
    from utils import export as ex
    from utils import export_formats as exf

    tmp_db = os.path.join(tmp, "chemeln.db")
    src = sqlite3.connect(f"file:{database.DB_PATH}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp_db)
    src.backup(dst)
    src.close()
    dst.close()
    database.DB_PATH = ex.DB_PATH = exf.DB_PATH = tmp_db
    if demo:
        print(f"[demo] 已为 {inject_demo_volumes(tmp_db)} 行投料补上体积（仅临时副本）")

    # 自动备份线程 → no-op（main.startup 里是函数内 import，替换模块属性即可生效）
    import utils.auto_backup as ab
    ab.start_scheduler = lambda *a, **k: None

    probe_path = os.path.join(ROOT, "frontend", "__probe.html")
    with open(os.path.join(ROOT, "frontend", "index.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", PROBE_JS.replace("EXP_ID", str(exp_id)) + "</body>")
    with open(probe_path, "w", encoding="utf-8") as f:
        f.write(html)

    out_dir = os.path.join(os.path.dirname(ROOT), "chemeln-backups", "投料表数值格式预览")
    os.makedirs(out_dir, exist_ok=True)

    import uvicorn
    import main as M
    cfg = uvicorn.Config(M.app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(cfg)
    threading.Thread(target=server.run, daemon=True).start()

    shots = []
    try:
        if not wait_ready():
            print("服务未就绪，放弃截图")
            return 1
        edge = find_edge()
        if not edge:
            print("未找到 Edge，放弃截图")
            return 1
        for tab, name in (("structure", "反应与结构"), ("reagents", "投料表-编辑区"),
                          ("content", "实验内容-投料汇总")):
            suffix = "-体积示例" if demo else ""
            out = os.path.join(out_dir, f"前端-{name}{suffix}.png")
            subprocess.run([
                edge, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--window-size=2300,900", "--virtual-time-budget=12000",
                f"--screenshot={out}",
                f"http://127.0.0.1:{PORT}/static/__probe.html#{tab}",
            ], capture_output=True, timeout=120)
            shots.append(out)
            print("已截图:", out)
    finally:
        server.should_exit = True
        time.sleep(0.5)
        if os.path.exists(probe_path):
            os.remove(probe_path)
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if shots else 1


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "demo"]
    eid = int(args[0]) if args else 20
    sys.exit(main(eid, demo="demo" in sys.argv))
