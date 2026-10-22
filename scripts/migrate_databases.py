#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三应用数据库归一迁移工具（P1 数据层基础设施）。

把三个独立 SQLite 库合并为一个统一库：

    黄河 ChemELN   %APPDATA%\\HuangheChemELN\\data.db
    合迹 ChemELN   %APPDATA%\\ChemELN\\chemeln.db
    合成工具箱     %APPDATA%\\com.heji.toolbox\\heji_toolbox.db
                        ↓
    合记 ChemLab   %APPDATA%\\ChemLab\\chemlab.db

设计原则
--------
1. **源库只读** —— 全程不写源库，迁移失败可无限重试。
2. **默认 dry-run** —— 必须显式 `--apply` 才会写目标库。
3. **幂等** —— 目标库加 `source_app + source_id` 唯一约束，
   重复执行不产生重复数据。
4. **可回溯** —— 目标库保留 `source_app` 与 `source_id`，
   任何一行都能找到它在原库中的出处。
5. **可对账** —— 逐表输出源行数 / 目标行数 / 差异清单。

用法
----
    # 1. 先看报告（只读，不写任何东西）
    python scripts/migrate_databases.py --report

    # 2. 校验源库可读性与结构
    python scripts/migrate_databases.py --verify

    # 3. 真正迁移（会备份三源库到目标目录 backups/migrate_<ts>/）
    python scripts/migrate_databases.py --apply

    # 4. 迁移后对账
    python scripts/migrate_databases.py --verify --target %APPDATA%\\ChemLab\\chemlab.db

字段冲突处理规则详见 docs/三应用整合方案.md 第 4.5 节。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

# 统一 schema 与 FTS 工具的单一真源在 backend/ 下，避免两处定义漂移。
# 本脚本是独立可执行的工具，因此显式把 backend/ 加入 sys.path。
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from schema_unified import SCHEMA          # noqa: E402
from utils.fts import (                     # noqa: E402
    spaced, rebuild_fts, build_match_query,
)

# ---------------------------------------------------------------- 常量

APP_NAME_EN = "ChemLab"

SOURCES = {
    "huanghe": {
        "label": "黄河 ChemELN",
        "db": Path(os.environ.get("APPDATA", "")) / "HuangheChemELN" / "data.db",
        "version": "0.1.3",
    },
    "chemeln": {
        "label": "合迹 ChemELN",
        "db": Path(os.environ.get("APPDATA", "")) / "ChemELN" / "chemeln.db",
        "version": "1.3.0",
    },
    "toolbox": {
        "label": "合成工具箱",
        "db": Path(os.environ.get("APPDATA", "")) / "com.heji.toolbox" / "heji_toolbox.db",
        "version": "0.11.2",
    },
}

DEFAULT_TARGET = Path(os.environ.get("APPDATA", "")) / APP_NAME_EN / "chemlab.db"

# 迁移顺序：先建 projects/compounds（被 experiments 引用），再迁 experiments
MIGRATION_ORDER = ["projects", "compounds", "experiments", "settings"]

# status 枚举归一映射（详见方案 4.5.2）
STATUS_MAP = {
    # 黄河
    "draft": "draft",
    # 合迹（已是目标值）
    "ongoing": "ongoing",
    "completed": "completed",
    "archived": "archived",
    # 工具箱
    "planned": "draft",
    "running": "ongoing",
    "finished": "completed",
    "aborted": "aborted",
}


# ---------------------------------------------------------------- 目标 schema

# 「合迹独有表」迁入时的源→目标字段名映射。
# 黄河的 attachments 用 note，目标表用 description —— 这是真实的字段名冲突，
# 逐一列出而非猜测，避免静默丢字段。
COLUMN_ALIASES = {
    "attachments": {"note": "description"},
}



# ---------------------------------------------------------------- 工具函数

def log(msg: str):
    print(msg, flush=True)


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    except sqlite3.Error:
        return 0


def norm_status(raw, default="draft") -> str:
    """status 归一：未知值落 default 并告警。"""
    if raw is None:
        return default
    key = str(raw).strip().lower()
    return STATUS_MAP.get(key, default)


def safe_json(value, default="[]"):
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    if not text:
        return default
    # 校验是否为合法 JSON；不是则包成字符串列表
    try:
        json.loads(text)
        return text
    except (ValueError, TypeError):
        return json.dumps([text], ensure_ascii=False)


_TARGET_COLUMNS = {}


def target_columns(conn: sqlite3.Connection, table: str) -> set:
    """目标库某表的列名集合（带缓存，避免每行都查 PRAGMA）。"""
    if table not in _TARGET_COLUMNS:
        _TARGET_COLUMNS[table] = {
            d[1] for d in conn.execute(f'PRAGMA table_info("{table}")')
        }
    return _TARGET_COLUMNS[table]


# ---------------------------------------------------------------- 报告

def cmd_report(args):
    """只读：列出三源库的表与数据量。"""
    log("=" * 68)
    log("三源数据库清单（只读，不写任何文件）")
    log("=" * 68)
    grand = 0
    for key, meta in SOURCES.items():
        db: Path = meta["db"]
        log("")
        log(f"[{meta['label']}]  {meta['version']}")
        log(f"  {db}")
        if not db.exists():
            log("  !! 文件不存在（该应用可能未运行过）")
            continue
        size = db.stat().st_size
        grand += size
        log(f"  大小: {size:,} bytes")
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            log(f"  !! 无法打开: {e}")
            continue
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        log(f"  表数: {len(tables)}")
        for t in tables:
            n = count(conn, t)
            if n > 0:
                cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
                log(f"    {t:<24} {n:>6} 行")
                log(f"      字段: {', '.join(cols)}")
        others = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('view','trigger') "
            "AND name NOT LIKE 'sqlite_%'")]
        if others:
            log(f"  视图/触发器: {', '.join(others)}")
        conn.close()

    log("")
    log("=" * 68)
    log(f"三库合计: {grand:,} bytes")
    log("=" * 68)
    return 0


def cmd_verify(args):
    """只读：校验源库可读 + 目标库（若已迁移）对账。"""
    log("=" * 68)
    log("迁移校验")
    log("=" * 68)

    problems = []
    for key, meta in SOURCES.items():
        db: Path = meta["db"]
        if not db.exists():
            problems.append(f"{meta['label']}: 数据库不存在")
            continue
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            conn.execute("SELECT 1").fetchone()
            conn.close()
            log(f"  OK   {meta['label']} 可读")
        except sqlite3.Error as e:
            problems.append(f"{meta['label']}: 无法读取 ({e})")
            log(f"  FAIL {meta['label']}: {e}")

    target = Path(args.target)
    if target.exists():
        log("")
        log(f"目标库: {target}")
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        log(f"  表数: {len(tables)}")
        for t in tables:
            n = count(conn, t)
            if n > 0:
                log(f"    {t:<24} {n:>6} 行")
        # 按来源统计
        log("")
        log("  按来源统计 experiments:")
        try:
            rows = conn.execute(
                "SELECT source_app, COUNT(*) c FROM experiments GROUP BY source_app"
            ).fetchall()
            for r in rows:
                log(f"    {r['source_app']:<12} {r['c']:>6}")
        except sqlite3.Error:
            log("    (experiments 表不存在)")
        conn.close()
    else:
        log("")
        log(f"目标库尚未创建: {target}")

    log("")
    if problems:
        log("发现问题:")
        for p in problems:
            log(f"  - {p}")
        return 1
    log("校验通过 ✅")
    return 0


# ---------------------------------------------------------------- 迁移

def backup_sources(target: Path) -> Path:
    """把三源库打成 zip，放到目标库同级的 backups/migrate_<ts>/。"""
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = target.parent / "backups" / f"migrate_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for key, meta in SOURCES.items():
        db: Path = meta["db"]
        if db.exists():
            dest = backup_dir / f"{key}_{db.name}"
            shutil.copy2(db, dest)
            log(f"  已备份 {meta['label']} -> {dest}")
    return backup_dir


def create_schema(conn: sqlite3.Connection):
    """建统一 schema。

    SCHEMA 来自 backend/schema_unified.py（单一真源）。
    FTS 索引不在此处建触发器 —— 中文分词采用 Python 侧 spaced() 处理，
    由 backend/utils/fts.py 的 rebuild_fts() 负责，见该模块文档。
    """
    conn.executescript(SCHEMA)
    conn.commit()


def migrate_source(conn: sqlite3.Connection, key: str, meta: dict) -> dict:
    """迁移单个源库。返回统计。"""
    db: Path = meta["db"]
    stats = {"label": meta["label"], "tables": {}}
    if not db.exists():
        log(f"  [跳过] {meta['label']}：数据库不存在")
        return stats

    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    # ---- 1. projects（黄河有，合迹是文本）----
    if table_exists(src, "projects"):
        rows = src.execute("SELECT * FROM projects").fetchall()
        n = 0
        for r in rows:
            existing = conn.execute(
                "SELECT id FROM projects WHERE source_app=? AND source_id=?",
                (key, r["id"])).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO projects (name, description, source_app, source_id, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (r["name"] or f"未命名项目", r["description"] or "",
                 key, r["id"], r["created_at"], r["updated_at"]))
            n += 1
        stats["tables"]["projects"] = n
        log(f"    projects       {n:>4} 行")

    # ---- 2. compounds（黄河 materials + 合迹 compounds）----
    src_table = None
    if table_exists(src, "compounds"):
        src_table = "compounds"
    elif table_exists(src, "materials"):
        src_table = "materials"
    if src_table:
        rows = src.execute(f"SELECT * FROM {src_table}").fetchall()
        n = 0
        merged = 0   # 因 CAS 重复而并入已有记录的数量
        for r in rows:
            existing = conn.execute(
                "SELECT id FROM compounds WHERE source_app=? AND source_id=?",
                (key, r["id"])).fetchone()
            if existing:
                continue
            # 幂等：已被 CAS 合并处理过的源记录，直接跳过
            audited = conn.execute(
                "SELECT target_id FROM migration_audit "
                "WHERE source_app=? AND source_table=? AND source_id=?",
                (key, src_table, r["id"])).fetchone()
            if audited:
                continue
            keys = r.keys()
            # 字段名归一：黄河 mol_weight/note → mw/notes
            mw = r["mw"] if "mw" in keys else r["mol_weight"]
            notes = r["notes"] if "notes" in keys else r["note"]
            aliases = safe_json(r["aliases"] if "aliases" in keys else None)
            inchi = r["inchi"] if "inchi" in keys else ""
            inchikey = r["inchikey"] if "inchikey" in keys else ""
            molfile = r["molfile"] if "molfile" in keys else ""
            density = r["density"] if "density" in keys else None
            purity = r["purity"] if "purity" in keys else 1.0
            updated = r["updated_at"] if "updated_at" in keys else r["created_at"]
            cas = (r["cas"] or "").strip()

            # CAS 去重：若目标库已有同 CAS 的化合物，则合并而非新建。
            # 合并策略（保守，不覆盖已有值）：
            #   - 化学实体字段（smiles/inchi/inchikey/molfile/mw/formula）：
            #     已有则保留，缺失则用新值补齐
            #   - 备注/别名/分类：追加合并
            #   - 库房信息（supplier/batch_no/location）：始终新增一行 compound_sources
            dup = None
            if cas:
                dup = conn.execute(
                    "SELECT id, smiles, inchi, inchikey, molfile, mw, formula "
                    "FROM compounds WHERE cas=? LIMIT 1", (cas,)).fetchone()

            if dup:
                dup_id = dup[0]
                # 补齐缺失的化学字段
                fills = []
                if not (dup[1] or "").strip() and (r["smiles"] or "").strip():
                    fills.append(("smiles", r["smiles"]))
                if not (dup[2] or "").strip() and (inchi or "").strip():
                    fills.append(("inchi", inchi))
                if not (dup[3] or "").strip() and (inchikey or "").strip():
                    fills.append(("inchikey", inchikey))
                if not (dup[4] or "").strip() and (molfile or "").strip():
                    fills.append(("molfile", molfile))
                if dup[5] is None and mw is not None:
                    fills.append(("mw", mw))
                if not (dup[6] or "").strip() and (r["formula"] or "").strip():
                    fills.append(("formula", r["formula"]))
                for col, val in fills:
                    conn.execute(f'UPDATE compounds SET "{col}"=? WHERE id=?',
                                 (val, dup_id))
                if fills:
                    log(f"    ~ CAS {cas} 已存在(id={dup_id})，补齐 {len(fills)} 个字段")
                conn.execute(
                    "INSERT OR REPLACE INTO migration_audit "
                    "(source_app, source_table, source_id, target_table, target_id, "
                    "action, note) VALUES (?,?,?,?,?,?,?)",
                    (key, src_table, r["id"], "compounds", dup_id,
                     "merged_by_cas", f"补齐 {len(fills)} 字段"))
                merged += 1
                new_id = dup_id
            else:
                conn.execute(
                    "INSERT INTO compounds (name, aliases, cas, smiles, inchi, inchikey, "
                    "molfile, mw, formula, density, purity, notes, category, created_at, "
                    "updated_at, source_app, source_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["name"] or "", aliases, cas, r["smiles"] or "",
                     inchi or "", inchikey or "", molfile or "", mw, r["formula"] or "",
                     density, purity, notes or "",
                     r["category"] or "general", r["created_at"], updated, key, r["id"]))
                new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT OR REPLACE INTO migration_audit "
                    "(source_app, source_table, source_id, target_table, target_id, "
                    "action, note) VALUES (?,?,?,?,?,?,?)",
                    (key, src_table, r["id"], "compounds", new_id, "inserted", ""))
                n += 1

            # 黄河的库房字段 → compound_sources 附属表
            if src_table == "materials":
                has_supplier = ("supplier" in keys and r["supplier"]) or \
                               ("batch_no" in keys and r["batch_no"]) or \
                               ("location" in keys and r["location"])
                if has_supplier:
                    conn.execute(
                        "INSERT INTO compound_sources (compound_id, supplier, batch_no, "
                        "location) VALUES (?,?,?,?)",
                        (new_id, r["supplier"] if "supplier" in keys else "",
                         r["batch_no"] if "batch_no" in keys else "",
                         r["location"] if "location" in keys else ""))
            # 注意：n 的自增已在上面 if/else 两个分支各自完成，
            # 这里不能再自增，否则每行会被计两次。
        stats["tables"]["compounds"] = n
        if merged:
            log(f"    compounds       {n:>4} 行  (源自 {src_table}，"
                f"另 {merged} 条因 CAS 重复并入已有记录)")
        else:
            log(f"    compounds       {n:>4} 行  (源自 {src_table})")

    # ---- 3. experiments ----
    if table_exists(src, "experiments"):
        rows = src.execute("SELECT * FROM experiments").fetchall()
        n = 0
        for r in rows:
            existing = conn.execute(
                "SELECT id FROM experiments WHERE source_app=? AND source_id=?",
                (key, r["id"])).fetchone()
            if existing:
                continue
            keys = r.keys()
            # 字段名归一：黄河 procedure → procedure（已是目标名）；
            # 工具箱 steps → procedure
            procedure = r["procedure"] if "procedure" in keys else (
                r["steps"] if "steps" in keys else "")
            content = r["content"] if "content" in keys else ""
            project = r["project"] if "project" in keys else ""
            code = r["code"] if "code" in keys else None
            project_id = r["project_id"] if "project_id" in keys else None
            # project_id 是源库主键，需映射到目标库 projects.id
            if project_id:
                mapped = conn.execute(
                    "SELECT id FROM projects WHERE source_app=? AND source_id=?",
                    (key, project_id)).fetchone()
                project_id = mapped[0] if mapped else None
            fk_cid = r["fk_compound_id"] if "fk_compound_id" in keys else None
            if fk_cid:
                mapped = conn.execute(
                    "SELECT id FROM compounds WHERE source_app=? AND source_id=?",
                    (key, fk_cid)).fetchone()
                fk_cid = mapped[0] if mapped else None
            sop_id = r["sop_id"] if "sop_id" in keys else None
            photos = safe_json(r["photos"] if "photos" in keys else None)
            started = r["started_at"] if "started_at" in keys else None
            finished = r["finished_at"] if "finished_at" in keys else None
            purity = r["purity_pct"] if "purity_pct" in keys else None
            reaction_json = r["reaction_json"] if "reaction_json" in keys else ""

            conn.execute(
                "INSERT INTO experiments (title, code, project_id, project, content, "
                "status, exp_date, purpose, procedure, observation, conclusion, "
                "reactants, reaction_json, sop_id, photos, yield_pct, purity_pct, "
                "target_compound, fk_compound_id, started_at, finished_at, notes, "
                "created_at, updated_at, source_app, source_id, step_no) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["title"] or "Untitled", code, project_id, project, content,
                 norm_status(r["status"]), r["exp_date"] or "",
                 r["purpose"] if "purpose" in keys else "",
                 procedure or "",
                 r["observation"] if "observation" in keys else "",
                 r["conclusion"] if "conclusion" in keys else "",
                 safe_json(r["reactants"] if "reactants" in keys else None),
                 reaction_json, sop_id, photos, r["yield_pct"], purity,
                 r["target_compound"] if "target_compound" in keys else "",
                 fk_cid, started, finished,
                 r["notes"] if "notes" in keys else "",
                 r["created_at"], r["updated_at"], key, r["id"],
                 r["step_no"] if "step_no" in keys else None))
            n += 1
        stats["tables"]["experiments"] = n
        log(f"    experiments     {n:>4} 行")

    # ---- 4. settings（三库同构，key 加前缀防冲突）----
    if table_exists(src, "settings"):
        rows = src.execute("SELECT * FROM settings").fetchall()
        n = 0
        for r in rows:
            k = r["key"]
            v = r["value"]
            prefixed = f"{key}.{k}"
            existing = conn.execute(
                "SELECT key FROM settings WHERE key=?", (prefixed,)).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO settings (key, value, source_app) VALUES (?,?,?)",
                (prefixed, v, key))
            n += 1
        stats["tables"]["settings"] = n
        log(f"    settings        {n:>4} 行  (key 已加 {key}. 前缀)")

    # ---- 5. 合迹独有表：整体迁入 ----
    for table in ("reagents", "reactions", "templates", "tags",
                  "attachments", "versions", "experiment_links"):
        if not table_exists(src, table):
            continue
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        n = 0
        for r in rows:
            existing = conn.execute(
                f"SELECT id FROM {table} WHERE source_app=? AND source_id=?",
                (key, r["id"])).fetchone()
            if existing:
                continue
            # PRAGMA table_info 返回 (cid, name, type, notnull, dflt, pk)
            # 注意取 d[1]（列名），不是 d[0]（cid）
            cols = [d[1] for d in src.execute(f"PRAGMA table_info({table})")]
            # 字段名归一（如黄河 attachments.note → description）
            aliases = COLUMN_ALIASES.get(table, {})
            tgt_cols = target_columns(conn, table)
            payload_cols = []
            for c in cols:
                if c == "id":
                    continue
                target_col = aliases.get(c, c)
                # 只迁目标表真实存在的列，其余记入警告
                if target_col not in tgt_cols:
                    log(f"    ! 跳过未知字段 {table}.{c}")
                    continue
                payload_cols.append((c, target_col))
            if not payload_cols:
                continue
            placeholders = ",".join("?" * len(payload_cols)) + ",?,?"
            col_names = ",".join(f'"{t}"' for _, t in payload_cols)
            conn.execute(
                f'INSERT INTO {table} ({col_names}, source_app, source_id) '
                f'VALUES ({placeholders})',
                tuple(r[s] for s, _ in payload_cols) + (key, r["id"]))
            n += 1
        stats["tables"][table] = n
        log(f"    {table:<16} {n:>4} 行")

    # ---- 6. 工具箱独有：experiment_steps ----
    if table_exists(src, "experiment_steps"):
        rows = src.execute("SELECT * FROM experiment_steps").fetchall()
        n = 0
        for r in rows:
            existing = conn.execute(
                "SELECT id FROM experiment_steps WHERE source_app=? AND source_id=?",
                (key, r["id"])).fetchone()
            if existing:
                continue
            # experiment_id 是源库主键，需映射
            mapped = conn.execute(
                "SELECT id FROM experiments WHERE source_app=? AND source_id=?",
                (key, r["experiment_id"])).fetchone()
            exp_id = mapped[0] if mapped else None
            if exp_id is None:
                continue  # 孤儿步骤，跳过
            conn.execute(
                "INSERT INTO experiment_steps (experiment_id, step_index, step_text, "
                "checked, note, photo_path, checked_at, source_app, source_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (exp_id, r["step_index"], r["step_text"], r["checked"],
                 r["note"], r["photo_path"], r["checked_at"], key, r["id"]))
            n += 1
        stats["tables"]["experiment_steps"] = n
        log(f"    experiment_steps {n:>3} 行")

    src.close()
    return stats


def cmd_apply(args):
    """执行迁移（写目标库）。"""
    target = Path(args.target)

    # 安全检查：目标库不能是任何源库
    for key, meta in SOURCES.items():
        if target.resolve() == meta["db"].resolve():
            log(f"!! 拒绝执行：目标路径与源库相同（{meta['label']}）")
            return 1

    log("=" * 68)
    log("开始迁移")
    log("=" * 68)
    log(f"目标库: {target}")

    # 1. 备份三源库
    log("")
    log("[1/4] 备份源库")
    backup_dir = backup_sources(target)
    log(f"  备份目录: {backup_dir}")

    # 2. 建目标 schema
    log("")
    log("[2/4] 创建目标 schema")
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    create_schema(conn)
    log("  schema 已就绪")

    # 3. 逐源迁移
    log("")
    log("[3/4] 迁移数据")
    all_stats = {}
    for key, meta in SOURCES.items():
        log(f"  [{meta['label']}]")
        all_stats[key] = migrate_source(conn, key, meta)
    conn.commit()

    # 4. 重建 FTS + 对账
    log("")
    log("[4/4] 重建全文索引与对账")
    try:
        fts_stats = rebuild_fts(conn)
        log(f"  experiments_fts 已重建（{fts_stats['experiments_fts']} 行）")
        log(f"  compounds_fts   已重建（{fts_stats['compounds_fts']} 行）")
    except sqlite3.Error as e:
        log(f"  !! FTS 重建失败: {e}")
    conn.commit()

    log("")
    log("  目标库统计:")
    for t in ("projects", "compounds", "compound_sources", "experiments",
              "reagents", "reactions", "templates", "tags", "attachments",
              "versions", "experiment_links", "experiment_steps", "settings"):
        n = count(conn, t)
        if n > 0:
            log(f"    {t:<20} {n:>6} 行")

    # 与源库对账
    log("")
    log("  对账（源 vs 目标）:")
    mismatch = 0
    for key, meta in SOURCES.items():
        db: Path = meta["db"]
        if not db.exists():
            continue
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for table in ("experiments", "compounds", "materials", "settings"):
            if not table_exists(src, table):
                continue
            src_n = count(src, table)
            tgt_table = "compounds" if table == "materials" else table
            tgt_n = conn.execute(
                f"SELECT COUNT(*) FROM {tgt_table} WHERE source_app=?", (key,)
            ).fetchone()[0]
            flag = "OK " if src_n == tgt_n else "差异"
            if src_n != tgt_n:
                mismatch += 1
            log(f"    {flag} {meta['label']:<12} {table:<12} 源 {src_n:>5} / 目标 {tgt_n:>5}")
        src.close()

    conn.close()

    log("")
    log("=" * 68)
    if mismatch:
        log(f"迁移完成，但有 {mismatch} 处计数差异（见上表，可能是孤儿记录被跳过）")
    else:
        log("迁移完成，计数全部一致 ✅")
    log(f"备份保留在: {backup_dir}")
    log("=" * 68)
    return 0


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="三应用数据库归一迁移",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="默认 dry-run（只读）。真正执行必须加 --apply。")
    ap.add_argument("--report", action="store_true",
                    help="列出三源库的表与数据量（只读）")
    ap.add_argument("--verify", action="store_true",
                    help="校验源库可读性 + 目标库对账")
    ap.add_argument("--apply", action="store_true",
                    help="执行迁移（会先备份三源库）")
    ap.add_argument("--target", default=str(DEFAULT_TARGET),
                    help=f"目标库路径（默认 {DEFAULT_TARGET}）")
    args = ap.parse_args()

    if not (args.report or args.verify or args.apply):
        ap.print_help()
        return 0

    if args.report:
        return cmd_report(args)
    if args.verify:
        return cmd_verify(args)
    if args.apply:
        return cmd_apply(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
