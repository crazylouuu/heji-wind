"""Search router — full-text search + tags + projects."""
from fastapi import APIRouter
from database import get_db
from utils.fts import build_match_query

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/fulltext")
def fulltext_search(q: str, limit: int = 50, scope: str = "all"):
    """SQLite FTS5 full-text search across experiments AND compounds.

    中文分词说明：统一库的 FTS 采用「汉字间插空格」方案，
    查询词必须经 build_match_query() 处理，否则中文查不到。
    详见 utils/fts.py 的模块文档。

    参数 scope：
        all       实验 + 化合物（默认）
        experiments  只搜实验记录
        compounds   只搜化合物库

    为什么默认搜化合物：整合后的库里 compounds 有 326 条（含黄河 256 条
    中文名物料），用户搜「乙醇」「甲苯」时期望能找到物料，而不只是实验记录。
    原 chemELN 版只搜实验 —— 那时库里化合物少，现在不够用了。
    """
    db = get_db()
    fts_query = build_match_query(q)   # 含 spaced() 处理 + 引号包裹

    exp_rows = []
    comp_rows = []

    want_exp = scope in ("all", "experiments")
    want_comp = scope in ("all", "compounds")

    # --- 实验记录 ---
    if want_exp:
        if fts_query:
            try:
                exp_rows = db.execute(
                    """SELECT e.id, e.title, snippet(experiments_fts, 1, '<mark>', '</mark>', '...', 20) as snippet,
                              e.project, e.status, e.updated_at
                       FROM experiments_fts
                       JOIN experiments e ON e.id = experiments_fts.rowid
                       WHERE experiments_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (fts_query, limit)).fetchall()
            except Exception:
                exp_rows = []
        if not exp_rows:
            # Fallback to LIKE search（也覆盖「查询词为空」或 FTS 报错的场景）
            exp_rows = db.execute(
                """SELECT e.id, e.title,
                          substr(e.content, max(1, instr(e.content, ?) - 50), 100) as snippet,
                          e.project, e.status, e.updated_at
                   FROM experiments e
                   WHERE e.title LIKE ? OR e.content LIKE ? OR e.notes LIKE ? OR e.target_compound LIKE ?
                   ORDER BY e.updated_at DESC LIMIT ?""",
                (q, f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", limit)).fetchall()

    # --- 化合物库 ---
    if want_comp:
        if fts_query:
            try:
                comp_rows = db.execute(
                    """SELECT c.id, c.name, c.cas, c.formula, c.category,
                              snippet(compounds_fts, 0, '<mark>', '</mark>', '...', 20) as snippet
                       FROM compounds_fts
                       JOIN compounds c ON c.id = compounds_fts.rowid
                       WHERE compounds_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (fts_query, limit)).fetchall()
            except Exception:
                comp_rows = []
        if not comp_rows:
            comp_rows = db.execute(
                """SELECT id, name, cas, formula, category, '' as snippet
                   FROM compounds
                   WHERE name LIKE ? OR cas LIKE ? OR notes LIKE ? OR formula LIKE ?
                   ORDER BY name LIMIT ?""",
                (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", limit)).fetchall()

    db.close()
    return {
        "query": q,
        "scope": scope,
        "results": [dict(r) for r in exp_rows],
        "compounds": [dict(r) for r in comp_rows],
        "count": len(exp_rows) + len(comp_rows),
    }


@router.get("/advanced")
def advanced_search(
    q: str = "",
    project: str = "",
    status: str = "",
    tag: str = "",
    target_compound: str = "",
    min_yield: float = None,
    max_yield: float = None,
    min_purity: float = None,
    max_purity: float = None,
    date_from: str = "",
    date_to: str = "",
    limit: int = 100,
):
    """Structured field query with multiple filters."""
    db = get_db()
    conditions = []
    params = []

    if q:
        conditions.append("(e.title LIKE ? OR e.content LIKE ? OR e.notes LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    if project:
        conditions.append("e.project = ?")
        params.append(project)
    if status:
        conditions.append("e.status = ?")
        params.append(status)
    if target_compound:
        conditions.append("e.target_compound LIKE ?")
        params.append(f"%{target_compound}%")
    if min_yield is not None:
        conditions.append("e.yield_pct >= ?")
        params.append(min_yield)
    if max_yield is not None:
        conditions.append("e.yield_pct <= ?")
        params.append(max_yield)
    if min_purity is not None:
        conditions.append("e.purity_pct >= ?")
        params.append(min_purity)
    if max_purity is not None:
        conditions.append("e.purity_pct <= ?")
        params.append(max_purity)
    if date_from:
        conditions.append("e.exp_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("e.exp_date <= ?")
        params.append(date_to)

    query = "SELECT DISTINCT e.* FROM experiments e"
    if tag:
        query += " JOIN experiment_tags et ON et.experiment_id = e.id JOIN tags t ON t.id = et.tag_id"
        conditions.append("t.name = ?")
        params.append(tag)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY e.updated_at DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(query, params).fetchall()
    db.close()
    return {"results": [dict(r) for r in rows], "count": len(rows)}


@router.get("/tags")
def list_tags():
    """List all tags with experiment counts."""
    db = get_db()
    rows = db.execute(
        """SELECT t.*, COUNT(et.experiment_id) as exp_count
           FROM tags t
           LEFT JOIN experiment_tags et ON et.tag_id = t.id
           GROUP BY t.id
           ORDER BY t.name""").fetchall()
    db.close()
    return {"tags": [dict(r) for r in rows]}


@router.post("/tags")
def create_tag(data: dict):
    db = get_db()
    name = data.get("name", "").strip()
    color = data.get("color", "#4a90d9")
    if not name:
        db.close()
        return {"error": "Tag name required"}
    try:
        cursor = db.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name, color))
        tid = cursor.lastrowid
        db.commit()
    except Exception:
        # Tag exists
        existing = db.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        db.close()
        return {"id": existing["id"] if existing else None, "message": "Tag already exists"}
    db.close()
    return {"id": tid, "name": name, "color": color}


@router.get("/projects")
def list_projects():
    """List all distinct project names."""
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT project FROM experiments WHERE project != '' ORDER BY project").fetchall()
    db.close()
    return {"projects": [r["project"] for r in rows]}


@router.get("/stats")
def dashboard_stats():
    """Dashboard statistics."""
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM experiments").fetchone()["c"]
    by_status = {}
    for r in db.execute("SELECT status, COUNT(*) as c FROM experiments GROUP BY status").fetchall():
        by_status[r["status"]] = r["c"]

    by_project = {}
    for r in db.execute("SELECT project, COUNT(*) as c FROM experiments WHERE project != '' GROUP BY project").fetchall():
        by_project[r["project"]] = r["c"]

    compounds = db.execute("SELECT COUNT(*) as c FROM compounds").fetchone()["c"]
    templates = db.execute("SELECT COUNT(*) as c FROM templates").fetchone()["c"]

    # Recent activity
    recent = db.execute(
        "SELECT id, title, status, updated_at FROM experiments ORDER BY updated_at DESC LIMIT 10").fetchall()

    # Average yield
    avg_yield = db.execute(
        "SELECT AVG(yield_pct) as avg FROM experiments WHERE yield_pct IS NOT NULL").fetchone()

    db.close()
    return {
        "total_experiments": total,
        "by_status": by_status,
        "by_project": by_project,
        "total_compounds": compounds,
        "total_templates": templates,
        "avg_yield": round(avg_yield["avg"], 1) if avg_yield["avg"] else 0,
        "recent": [dict(r) for r in recent],
    }
