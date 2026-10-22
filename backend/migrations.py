# -*- coding: utf-8 -*-
"""
Schema migrations — versioned, idempotent, run once per database.

每个迁移是一个函数：接收 conn，做一次 ALTER/数据迁移。
函数本身幂等（先检查列是否存在再 ALTER），新库建表后跑迁移是空操作。

三应用整合后的变化（2026-10-22）
--------------------------------
统一 schema（backend/schema_unified.py）已**内置**下面 v1~v4 涉及的全部列
（compounds.category、templates.reaction_template、
reagents.ratio_type/ratio_value/mass_g、experiments.step_no）。

因此对新建的统一库而言，这些迁移是**空操作**——保留它们只是为了兼容
「用户本机已有旧 chemELN 库，直接升级到 ChemLab」的场景：
   旧库（12 表）→ init_db 建统一表 → 这些 ALTER 把缺的列补齐
   → 再由 scripts/migrate_databases.py 做数据归并

新增迁移时：
1. 在 MIGRATIONS 列表末尾追加一个新元组 (version, name, func)
2. version 必须严格递增
3. 函数里必须先检查列/表是否存在，再执行 ALTER
4. 同时把新列补进 backend/schema_unified.py（schema 是单一真源）
"""
from __future__ import annotations


def _has_column(conn, table: str, column: str) -> bool:
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})"))


def _v1_add_compounds_category(conn):
    """v1: compounds 表加 category 列（project/common 分类）"""
    if not _has_column(conn, "compounds", "category"):
        conn.execute("ALTER TABLE compounds ADD COLUMN category TEXT DEFAULT 'project'")


def _v2_add_templates_reaction_template(conn):
    """v2: templates 表加 reaction_template 列"""
    if not _has_column(conn, "templates", "reaction_template"):
        conn.execute("ALTER TABLE templates ADD COLUMN reaction_template TEXT DEFAULT ''")


def _v3_add_reagents_ratio_and_mass_g(conn):
    """v3: reagents 表加 ratio_type / ratio_value / mass_g 列，并把 mass_mg 迁移到 mass_g"""
    if not _has_column(conn, "reagents", "ratio_type"):
        conn.execute("ALTER TABLE reagents ADD COLUMN ratio_type TEXT DEFAULT 'equiv'")
    if not _has_column(conn, "reagents", "ratio_value"):
        conn.execute("ALTER TABLE reagents ADD COLUMN ratio_value REAL")
    if not _has_column(conn, "reagents", "mass_g"):
        conn.execute("ALTER TABLE reagents ADD COLUMN mass_g REAL")
        conn.execute(
            "UPDATE reagents SET mass_g = mass_mg / 1000.0 "
            "WHERE mass_g IS NULL AND mass_mg IS NOT NULL")


def _v4_add_experiments_step_no(conn):
    """v4: experiments 表加 step_no 列（合成路线第几步）"""
    if not _has_column(conn, "experiments", "step_no"):
        conn.execute("ALTER TABLE experiments ADD COLUMN step_no INTEGER")


# 迁移注册表：(version, 名称, 函数)。version 必须严格递增，只追加不修改。
#
# ⚠️ 版本号从 5 起：1~4 是 chemELN 历史迁移，其效果已内置进
# backend/schema_unified.py，并在该文件的 schema_migrations 里预标记为已应用。
# 若把这里改成 1~4，会与预标记重复（INSERT OR IGNORE 不会报错，
# 但日志会误导）。
MIGRATIONS = [
    (1, "legacy: add compounds.category", _v1_add_compounds_category),
    (2, "legacy: add templates.reaction_template", _v2_add_templates_reaction_template),
    (3, "legacy: add reagents.ratio_type/ratio_value/mass_g", _v3_add_reagents_ratio_and_mass_g),
    (4, "legacy: add experiments.step_no", _v4_add_experiments_step_no),
    # --- ChemLab 自己的迁移从这里开始追加（version >= 5）---
]


def run_migrations(conn) -> list[str]:
    """执行所有未跑过的迁移。返回本次执行的迁移名称列表。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    INTEGER PRIMARY KEY,
            name       TEXT NOT NULL,
            applied_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    executed = []
    for version, name, func in MIGRATIONS:
        if version in applied:
            continue
        func(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name))
        executed.append(f"v{version}: {name}")
    if executed:
        conn.commit()
    return executed
