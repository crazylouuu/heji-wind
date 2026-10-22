"""
ChemLab Database —— 统一 schema 的运行时入口。

2026-10-22 三应用整合：原 chemELN 的 12 表 schema 已替换为
backend/schema_unified.py 定义的统一 schema（16 表，含 source_app/source_id
溯源列、projects、compound_sources、experiment_steps 等整合新增表）。

schema 的单一真源在 backend/schema_unified.py，本文件只负责建库、
迁移编排与初始数据播种。
"""
import sqlite3
import os
import json
from pathlib import Path

from config import DB_PATH, ATTACH_DIR
from schema_unified import SCHEMA
from migrations import run_migrations
from utils.fts import rebuild_fts



def get_db() -> sqlite3.Connection:
    """Return a connection with row_factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables and seed default data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(ATTACH_DIR, exist_ok=True)
    conn = get_db()
    conn.executescript(SCHEMA)

    # --- Versioned migrations (幂等，新库空操作) ---
    executed = run_migrations(conn)
    if executed:
        print("[DB] migrations applied: " + ", ".join(executed))


    # --- Seed built-in solvent & reagent libraries once ---
    seeded = conn.execute("SELECT value FROM settings WHERE key='seeded_common_libs'").fetchone()
    if not seeded:
        from utils.common_reagents import get_seeded_common_compounds
        seeded_n = 0
        for name, cas, formula, mw, category in get_seeded_common_compounds():
            # 查重要同时看 name 和 cas：
            # 整合后的库里可能已有从黄河/合迹迁入的同名或同 CAS 化合物
            # （例如「乙醇」在三个源库都存在），只按 name 判重会漏。
            exists = conn.execute(
                "SELECT 1 FROM compounds WHERE name=? COLLATE NOCASE OR cas=?",
                (name, cas)).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO compounds (name, cas, smiles, inchikey, mw, formula, "
                "notes, category, source_app, source_id) "
                "VALUES (?, ?, '', '', ?, ?, '内置常用库', ?, 'chemlab', NULL)",
                (name, cas, mw, formula, category))
            seeded_n += 1
        conn.execute(
            "INSERT INTO settings (key, value, source_app) "
            "VALUES ('seeded_common_libs', '1', 'chemlab')")
        print(f"[DB] Seeded {seeded_n} built-in compounds "
              f"(skipped duplicates by name/CAS)")

    # --- Seed default templates once (settings flag prevents re-insert on every restart) ---
    tpl_seeded = conn.execute("SELECT value FROM settings WHERE key='seeded_templates'").fetchone()
    if not tpl_seeded:
        default_templates = [
            ('通用反应模板', 'reaction',
             '<h2>实验目的</h2><p>...</p><h2>反应方程式</h2><p>[插入结构式]</p><h2>实验步骤</h2><ol><li>...</li></ol><h2>后处理</h2><ol><li>...</li></ol><h2>表征数据</h2><p>1H NMR: </p><p>13C NMR: </p><p>MS: </p>',
             '[{"role":"substrate","name":"","equivalents":1.0},{"role":"reagent","name":"","equivalatives":1.2},{"role":"solvent","name":"","equivalents":0}]'),
            ('后处理模板', 'workup',
             '<h2>萃取</h2><p>溶剂：; 次数：</p><h2>干燥</h2><p>干燥剂：</p><h2>浓缩</h2><p>方法：</p>',
             '[]'),
            ('结晶模板', 'crystallization',
             '<h2>溶剂体系</h2><p>良溶剂：; 不良溶剂：</p><h2>结晶条件</h2><p>温度：; 降温速率：</p><h2>结果</h2><p>晶体形态：; 收率：</p>',
             '[]'),
        ]
        for name, typ, content, rt in default_templates:
            exists = conn.execute(
                "SELECT 1 FROM templates WHERE name=? COLLATE NOCASE", (name,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO templates (name, type, content, reagent_template, "
                "source_app, source_id) VALUES (?,?,?,?, 'chemlab', NULL)",
                (name, typ, content, rt))
        conn.execute(
            "INSERT INTO settings (key, value, source_app) "
            "VALUES ('seeded_templates', '1', 'chemlab')")

    # --- 全文索引：播种后重建（spaced() 处理，见 utils/fts.py）---
    # 迁移脚本也会调 rebuild_fts，但后端启动时库可能是空的或刚播完种，
    # 这里统一兜底一次，保证 FTS 与主表一致。
    try:
        fts_stats = rebuild_fts(conn)
        print(f"[DB] FTS rebuilt: experiments={fts_stats['experiments_fts']}, "
              f"compounds={fts_stats['compounds_fts']}")
    except Exception as e:
        print(f"[DB] FTS rebuild skipped: {e}")

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
