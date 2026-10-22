# -*- coding: utf-8 -*-
"""ChemLab 统一数据库 schema（单一真源）。

本文件是三应用整合后的**唯一 schema 定义**，被两处引用：

    backend/database.py          后端运行时建库
    scripts/migrate_databases.py 三库归一迁移

**修改 schema 必须改这里**，不要在两处分别改，否则会漂移。

设计要点
--------
1. `source_app` + `source_id` 标记每行的来源应用与原始主键，
   配合 UNIQUE 约束实现幂等迁移，并保证任何一行可回溯到原库出处。
2. 字段名冲突的处理（详见 docs/三应用整合方案.md 4.5 节）：
   - 黄河 materials.mol_weight → compounds.mw
   - 黄河 materials.note      → compounds.notes
   - 黄河 experiments.procedure / 工具箱 experiments.steps → experiments.procedure
   - 黄河 attachments.note    → attachments.description
3. status 枚举归一为 5 态：draft/ongoing/completed/archived/aborted
   （工具箱的 planned→draft, running→ongoing, finished→completed, aborted→aborted）
4. 黄河的库房字段（supplier/batch_no/location）拆到 compound_sources 附属表，
   因为一个化合物可能对应多个批次。
5. 全文索引采用「汉字间插空格」方案，原因见 utils/fts.py 的模块文档。
"""

SCHEMA = """
-- 统一实验表：三源超集
CREATE TABLE IF NOT EXISTS experiments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT NOT NULL DEFAULT 'Untitled',
    code           TEXT,
    project_id     INTEGER REFERENCES projects(id),
    project        TEXT DEFAULT '',
    content        TEXT DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'draft',
    exp_date       TEXT DEFAULT '',
    purpose        TEXT DEFAULT '',
    procedure      TEXT DEFAULT '',
    observation    TEXT DEFAULT '',
    conclusion     TEXT DEFAULT '',
    reactants      TEXT DEFAULT '[]',
    reaction_json  TEXT DEFAULT '',
    sop_id         TEXT,
    photos         TEXT DEFAULT '[]',
    yield_pct      REAL,
    purity_pct     REAL,
    target_compound TEXT DEFAULT '',
    fk_compound_id INTEGER REFERENCES compounds(id),
    started_at     TEXT,
    finished_at    TEXT,
    notes          TEXT DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    source_app     TEXT NOT NULL DEFAULT 'chemlab',
    source_id      INTEGER,
    -- chemELN v4 迁移加的列（合成路线第几步），后端 experiments.py 有 15 处引用，
    -- 统一 schema 初期遗漏，2026-10-22 接入后端时发现并补回
    step_no        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_exp_status   ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_exp_project  ON experiments(project_id);
CREATE INDEX IF NOT EXISTS idx_exp_date     ON experiments(exp_date);

-- 统一物料/化合物表：黄河 materials 与合迹 compounds 超集
CREATE TABLE IF NOT EXISTS compounds (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT DEFAULT '',
    aliases    TEXT DEFAULT '[]',
    cas        TEXT DEFAULT '',
    smiles     TEXT DEFAULT '',
    inchi      TEXT DEFAULT '',
    inchikey   TEXT DEFAULT '',
    molfile    TEXT DEFAULT '',
    mw         REAL,
    formula    TEXT DEFAULT '',
    density    REAL,
    purity     REAL DEFAULT 1.00,
    notes      TEXT DEFAULT '',
    category   TEXT DEFAULT 'general',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    source_app TEXT NOT NULL DEFAULT 'chemlab',
    source_id  INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_comp_cas ON compounds(cas)
    WHERE cas IS NOT NULL AND cas <> '';
CREATE INDEX IF NOT EXISTS idx_comp_name ON compounds(name);

-- 黄河的库房/批次信息拆到附属表（一对多）
CREATE TABLE IF NOT EXISTS compound_sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_id INTEGER NOT NULL REFERENCES compounds(id) ON DELETE CASCADE,
    supplier    TEXT DEFAULT '',
    batch_no    TEXT DEFAULT '',
    location    TEXT DEFAULT '',
    quantity    REAL,
    unit        TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);

-- 项目表：黄河的 projects + 合迹的纯文本 project 去重后建表
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    source_app  TEXT NOT NULL,
    source_id   INTEGER,
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    updated_at  TEXT DEFAULT (datetime('now','localtime'))
);

-- 试剂投料表（合迹独有，整体迁入）
-- 注意：ratio_type / ratio_value / mass_g 是 chemELN v3 迁移加的列，
-- 后端 experiments.py 与 utils/export_formats.py 都在用，必须保留。
-- mass_g 是「克」，mass_mg 是「毫克」（旧字段，保留兼容）。
CREATE TABLE IF NOT EXISTS reagents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id  INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    role           TEXT DEFAULT '',
    compound_id    INTEGER REFERENCES compounds(id),
    name           TEXT DEFAULT '',
    smiles         TEXT DEFAULT '',
    mw             REAL,
    equivalents    REAL,
    mass_mg        REAL,
    mass_g         REAL,
    moles_mmol     REAL,
    volume_ml      REAL,
    density        REAL,
    concentration  REAL,
    purity_pct     REAL,
    ratio_type     TEXT DEFAULT 'equiv',
    ratio_value    REAL,
    sort_order     INTEGER DEFAULT 0,
    source_app     TEXT NOT NULL DEFAULT 'chemlab',
    source_id      INTEGER
);

-- 反应式表（合迹独有）
CREATE TABLE IF NOT EXISTS reactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id   INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    display_mode    TEXT DEFAULT 'scheme',
    reactant_smiles TEXT DEFAULT '[]',
    product_smiles  TEXT DEFAULT '[]',
    conditions      TEXT DEFAULT '',
    arrow_label     TEXT DEFAULT '',
    image_path      TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    sort_order      INTEGER DEFAULT 0,
    source_app      TEXT NOT NULL DEFAULT 'chemlab',
    source_id       INTEGER
);

-- 模板表（合迹独有）
CREATE TABLE IF NOT EXISTS templates (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    type              TEXT DEFAULT 'reaction',
    content           TEXT DEFAULT '',
    reagent_template  TEXT DEFAULT '',
    reaction_template TEXT DEFAULT '',
    created_at        TEXT DEFAULT (datetime('now','localtime')),
    source_app        TEXT NOT NULL DEFAULT 'chemlab',
    source_id         INTEGER
);

-- 标签（合迹独有）
CREATE TABLE IF NOT EXISTS tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    color      TEXT DEFAULT '#4a90d9',
    source_app TEXT NOT NULL DEFAULT 'chemlab',
    source_id  INTEGER
);
CREATE TABLE IF NOT EXISTS experiment_tags (
    experiment_id INTEGER REFERENCES experiments(id) ON DELETE CASCADE,
    tag_id        INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (experiment_id, tag_id)
);

-- 附件（黄河 + 合迹）
CREATE TABLE IF NOT EXISTS attachments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER REFERENCES experiments(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    file_type     TEXT DEFAULT '',
    file_size     INTEGER DEFAULT 0,
    description   TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now','localtime')),
    source_app    TEXT NOT NULL DEFAULT 'chemlab',
    source_id     INTEGER
);

-- 版本快照（合迹独有）
CREATE TABLE IF NOT EXISTS versions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER REFERENCES experiments(id) ON DELETE CASCADE,
    content       TEXT NOT NULL,
    reagents_json TEXT DEFAULT '[]',
    version_note  TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now','localtime')),
    source_app    TEXT NOT NULL DEFAULT 'chemlab',
    source_id     INTEGER
);

-- 实验关联（合迹独有）
CREATE TABLE IF NOT EXISTS experiment_links (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    from_exp     INTEGER REFERENCES experiments(id) ON DELETE CASCADE,
    to_exp       INTEGER REFERENCES experiments(id) ON DELETE CASCADE,
    link_type    TEXT DEFAULT 'related',
    source_app   TEXT NOT NULL DEFAULT 'chemlab',
    source_id    INTEGER
);

-- 步骤勾选（工具箱独有，与 reagents 并存 —— 语义不同，不合并）
CREATE TABLE IF NOT EXISTS experiment_steps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    step_index    INTEGER NOT NULL,
    step_text     TEXT NOT NULL,
    checked       INTEGER NOT NULL DEFAULT 0,
    note          TEXT NOT NULL DEFAULT '',
    photo_path    TEXT,
    checked_at    TEXT,
    source_app    TEXT NOT NULL DEFAULT 'chemlab',
    source_id     INTEGER
);

-- 设置：三库本就同构（key TEXT PK, value TEXT），直接合并，key 加来源前缀
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT,
    source_app TEXT NOT NULL DEFAULT 'chemlab'
);

-- 迁移审计
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ⚠️ 版本号约定（重要，避免重复执行迁移）
-- 本 schema 已内置 chemELN 历史 v1~v4 迁移涉及的全部列
-- （compounds.category / templates.reaction_template /
--   reagents.ratio_type,ratio_value,mass_g / experiments.step_no），
-- 因此这里**预标记** v1~v4 为已应用，后端 migrations.py 的
-- run_migrations() 就不会对新建的统一库重跑这些 ALTER。
--
-- 版本 5 起由 ChemLab 自己的迁移使用（见 backend/migrations.py）。
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (1, 'legacy: add compounds.category');
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (2, 'legacy: add templates.reaction_template');
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (3, 'legacy: add reagents.ratio_type/ratio_value/mass_g');
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (4, 'legacy: add experiments.step_no');
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (5, 'unified_from_three_apps');

-- CAS 合并审计：记录「哪条源记录被并入了哪条目标记录」。
-- 作用：实现幂等 —— 二次执行时先查这里，已合并过的直接跳过，
-- 不会反复走「补齐字段」流程（虽然不会产生重复数据，但白做功）。
CREATE TABLE IF NOT EXISTS migration_audit (
    source_app   TEXT NOT NULL DEFAULT 'chemlab',
    source_table TEXT NOT NULL,
    source_id    INTEGER,
    target_table TEXT NOT NULL,
    target_id    INTEGER NOT NULL,
    action       TEXT NOT NULL,          -- merged_by_cas | inserted | skipped
    note         TEXT DEFAULT '',
    migrated_at  TEXT DEFAULT (datetime('now','localtime'))
    -- 不用 PRIMARY KEY：SQLite 主键列隐含 NOT NULL，而 source_id 允许为 NULL
    -- （与其它表保持一致）。唯一性由下方 uq_audit_source 部分索引保证。
);

-- 全文索引（迁移后统一重建，见 rebuild_fts）
--
-- 中文分词方案说明（重要，2026-10-22 实测选型）
-- ---------------------------------------------------------------
-- 原三库用 FTS5 默认 unicode61 分词器，它把「连续中文串」当成**单个 token」，
-- 于是「苯甲酸酯化」整串才是一个词，搜「苯甲酸」「酯化」全部匹配不到 ——
-- 中文全文检索实际上一直是坏的（已在原库上复现确认，非本次迁移引入）。
--
-- 实测对比过两种方案（SQLite 3.53.1）：
--   A. unicode61 + 索引与查询都在汉字间插空格   → 10/10 命中 ✅ 采用
--   B. trigram 分词器（3.34+）                    → 3/10 命中 ❌
--      trigram 按 3 字符滑窗索引，2 字词与单字查询基本失效。
--
-- 方案 A 的原理：把「苯甲酸酯化」索引成「苯 甲 酸 酯 化」，
-- 每个汉字成为独立 token；查询侧同样处理后，
-- 「苯甲酸」→「苯 甲 酸」，FTS5 对多 token 默认做 AND 且要求相邻，
-- 因此既能命中完整词，也能命中「过氧苯甲酸」这类跨词子串。
--
-- ⚠️ 代价与约定：
--   * 查询侧**必须**走同一个 spaced() 处理，否则中文查不到。
--     统一封装在 backend/utils/fts.py 的 build_match_query()。
--   * 原有英文/数字/CAS 检索行为不变。
--
-- ⚠️ 为什么**不用** content='experiments' 外表模式（2026-10-22 实测踩坑）：
--   外表模式（external content）下，手工执行
--       DELETE FROM experiments_fts WHERE rowid=?
--   会报 `database disk image is malformed` —— 外表模式的索引由触发器
--   维护，应用层直接 DELETE 会破坏 FTS 内部结构。
--   而我们需要应用层同步（因为 spaced() 后的文本不能写回主表，
--   SQLite 也无正则替换函数可在触发器里调用）。
--   因此这里用**普通 FTS 表**（不带 content=），索引由
--   backend/utils/fts.py 的 sync_experiment()/rebuild_fts() 维护，
--   DELETE + INSERT 均正常。
CREATE VIRTUAL TABLE IF NOT EXISTS experiments_fts USING fts5(
    title, content, project, target_compound, notes
);

-- 化合物全文索引（统一库新增 —— 黄河库有 materials_fts，合迹库没有，统一后补上）
-- 分词方案同上：unicode61 + 汉字间插空格（见 spaced()）
-- 同样不用外表模式，原因同上。
CREATE VIRTUAL TABLE IF NOT EXISTS compounds_fts USING fts5(
    name, aliases, cas, formula, notes
);

-- ============================================================
-- 溯源唯一约束（部分索引）
-- ============================================================
-- 为什么用部分索引而不是表内 UNIQUE(source_app, source_id)：
--   source_id 是「原库主键」，只有迁移进来的记录才有。
--   ChemLab 原生新建的记录 source_id 为 NULL，且会有多条 ——
--   若用表内 UNIQUE，(NULL, 'chemlab') 会被 SQLite 视为互不相同而不冲突，
--   但 NOT NULL 约束又会让插入直接失败。
--   因此：source_id 允许为 NULL，并用部分唯一索引只在
--   「source_id 非空」时强制唯一，兼顾幂等迁移与原生新建。
CREATE UNIQUE INDEX IF NOT EXISTS uq_exp_source   ON experiments(source_app, source_id)      WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_comp_source  ON compounds(source_app, source_id)       WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_reag_source  ON reagents(source_app, source_id)        WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_rx_source    ON reactions(source_app, source_id)       WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_tpl_source   ON templates(source_app, source_id)       WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_tag_source   ON tags(source_app, source_id)            WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_att_source   ON attachments(source_app, source_id)     WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ver_source   ON versions(source_app, source_id)        WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_link_source  ON experiment_links(source_app, source_id) WHERE source_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_step_source  ON experiment_steps(source_app, source_id) WHERE source_id IS NOT NULL;

-- projects 的 name 唯一（一个项目名只应有一条，不论来源）
CREATE UNIQUE INDEX IF NOT EXISTS uq_project_name ON projects(name);

-- 迁移幂等：同一源记录只处理一次
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_source ON migration_audit(source_app, source_table, source_id);
"""
