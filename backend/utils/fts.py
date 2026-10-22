# -*- coding: utf-8 -*-
"""ChemLab 全文检索工具 —— 中文分词方案（单一真源）。

背景：一个真实的既有缺陷
------------------------
原三应用（黄河 ChemELN / 合迹 ChemELN / 合成工具箱）的 FTS 都用 SQLite FTS5
的**默认 unicode61 分词器**。该分词器把「连续中文串」当成**单个 token」：

    「苯甲酸酯化」→ 1 个 token: "苯甲酸酯化"

于是搜「苯甲酸」「酯化」永远匹配不到 —— 中文全文检索实际上是坏的。
（2026-10-22 已在原库上复现确认：搜「苯甲酸」「酯化」「实验」全部 0 条，
而非本次整合迁移引入的回归。）

方案选型（实测对比，SQLite 3.53.1）
----------------------------------
| 方案                              | 命中率    | 结论 |
| --------------------------------- | --------- | ---- |
| unicode61 + 索引与查询都插空格     | **10/10** | ✅ 采用 |
| trigram 分词器（SQLite 3.34+）     | 3/10      | ❌ 放弃 |

trigram 按 3 字符滑窗建索引，2 字词与单字查询基本失效
（实测「甲苯」「乙醇」「钾」「锰酸」全部 0 条）。

采用方案原理
------------
把「苯甲酸酯化」索引成「苯 甲 酸 酯 化」，每个汉字成为独立 token；
查询侧同样处理后，「苯甲酸」→「苯 甲 酸」。

FTS5 对多个 token 默认执行 AND 且要求**相邻**（implicit phrase），
因此：
  - 完整词「苯甲酸」能命中
  - 2 字词「甲苯」「乙醇」能命中
  - 单字「钾」能命中
  - 跨词子串「过氧苯甲酸」能命中「间氯过氧苯甲酸」
  - 英文/数字/CAS 行为不变（"water" "H2O" "65-85-0" 均正常）

⚠️ 使用约定（重要）
------------------
**索引侧与查询侧必须都走本模块的处理**，否则中文查不到：

    写入/重建索引  →  spaced()
    查询           →  build_match_query()

不要在别处直接写 `WHERE fts MATCH '苯甲酸'`，那一定查不到。

为什么不用 SQL 触发器自动同步
----------------------------
插空格后的文本不能写回 experiments/compounds 原表（会污染用户数据），
SQLite 也没有正则替换函数可在触发器里调用。因此：

  - 批量导入/迁移后：调 rebuild_fts() 全量重建
  - 日常增删改：调 sync_experiment() / sync_compound() 单条同步
    （后端 routers 在写入主表后调用）
"""
import re
import sqlite3

# 汉字范围：CJK 统一表意文字基本区 + 扩展A
# 扩展B（U+20000 起）在 Python 的 str 里是单个码位，正则可用
CJK_RE = re.compile(r"([\u4e00-\u9fff\U00020000-\U0002a6df])")

EXPERIMENT_FTS_COLS = ("title", "content", "project", "target_compound", "notes")
COMPOUND_FTS_COLS = ("name", "aliases", "cas", "formula", "notes")


def spaced(text) -> str:
    """汉字间插空格，使 unicode61 分词器把每个汉字当作独立 token。

    索引侧与查询侧都必须调用本函数。
    """
    if not text:
        return ""
    return CJK_RE.sub(lambda m: m.group(1) + " ", str(text))


def build_match_query(user_input: str) -> str:
    """把用户搜索词转成 FTS5 MATCH 表达式。

    - 汉字间插空格（与索引侧一致）
    - 每个 token 用双引号包裹，避免 FTS5 把 `-` `:` `(` 等当语法字符
      （例如 CAS 号 "65-85-0" 含连字符，直接 MATCH 会被当 NOT 运算符）

    返回空串表示无有效查询词，调用方应回退到 LIKE。
    """
    text = spaced(user_input).strip()
    if not text:
        return ""
    tokens = [t for t in text.split() if t]
    if not tokens:
        return ""
    return " ".join(f'"{t}"' for t in tokens)


def rebuild_fts(conn: sqlite3.Connection) -> dict:
    """全量重建两个 FTS 索引。幂等：先清空再重建。

    迁移/批量导入后调用。返回各表重建行数。

    注意：FTS 表是**非外表模式**（见 schema_unified.py 的说明），
    rowid 由 SQLite 自动分配。为了让 FTS 的 rowid 与主表 id 一致
    （JOIN 时 ON e.id = experiments_fts.rowid 才成立），
    这里显式插入 rowid，并用 OR REPLACE 避免与残留行冲突。
    """
    stats = {}
    for table in ("experiments_fts", "compounds_fts"):
        try:
            conn.execute(f"DELETE FROM {table}")
        except sqlite3.Error:
            pass

    rows = conn.execute(
        "SELECT id, title, content, project, target_compound, notes "
        "FROM experiments").fetchall()
    conn.executemany(
        "INSERT OR REPLACE INTO experiments_fts"
        "(rowid, title, content, project, target_compound, notes) "
        "VALUES (?,?,?,?,?,?)",
        [tuple([r[0]] + [spaced(r[i]) for i in range(1, 6)]) for r in rows])
    stats["experiments_fts"] = len(rows)

    rows = conn.execute(
        "SELECT id, name, aliases, cas, formula, notes FROM compounds").fetchall()
    conn.executemany(
        "INSERT OR REPLACE INTO compounds_fts"
        "(rowid, name, aliases, cas, formula, notes) VALUES (?,?,?,?,?,?)",
        [tuple([r[0]] + [spaced(r[i]) for i in range(1, 6)]) for r in rows])
    stats["compounds_fts"] = len(rows)
    conn.commit()
    return stats


def sync_experiment(conn: sqlite3.Connection, exp_id: int) -> None:
    """单条同步实验记录的 FTS 索引（增/改/删后调用）。

    rowid 显式设为 exp_id，保证与主表 id 一致。
    """
    row = conn.execute(
        "SELECT id, title, content, project, target_compound, notes "
        "FROM experiments WHERE id=?", (exp_id,)).fetchone()
    conn.execute("DELETE FROM experiments_fts WHERE rowid=?", (exp_id,))
    if row is None:
        return
    conn.execute(
        "INSERT OR REPLACE INTO experiments_fts"
        "(rowid, title, content, project, target_compound, notes) "
        "VALUES (?,?,?,?,?,?)",
        tuple([row[0]] + [spaced(row[i]) for i in range(1, 6)]))


def sync_compound(conn: sqlite3.Connection, compound_id: int) -> None:
    """单条同步化合物的 FTS 索引（增/改/删后调用）。"""
    row = conn.execute(
        "SELECT id, name, aliases, cas, formula, notes FROM compounds WHERE id=?",
        (compound_id,)).fetchone()
    conn.execute("DELETE FROM compounds_fts WHERE rowid=?", (compound_id,))
    if row is None:
        return
    conn.execute(
        "INSERT OR REPLACE INTO compounds_fts"
        "(rowid, name, aliases, cas, formula, notes) VALUES (?,?,?,?,?,?)",
        tuple([row[0]] + [spaced(row[i]) for i in range(1, 6)]))
