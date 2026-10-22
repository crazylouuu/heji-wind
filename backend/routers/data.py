"""Backup & import/export router."""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, PlainTextResponse
from database import get_db, DB_PATH, ATTACH_DIR
from utils.export import (export_experiment_markdown, export_experiment_html,
                           export_all_json,
                           export_experiments_excel, backup_database, import_from_csv)
import os, tempfile, shutil

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/export/experiment/{exp_id}/markdown")
def export_md(exp_id: int):
    md = export_experiment_markdown(exp_id)
    return PlainTextResponse(
        md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=experiment_{exp_id}.md"})


@router.get("/export/experiment/{exp_id}/html")
def export_html(exp_id: int):
    html = export_experiment_html(exp_id)
    return PlainTextResponse(
        html,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=experiment_{exp_id}.html"})


@router.get("/export/experiment/{exp_id}/pdf")
def export_pdf(exp_id: int):
    """Export a single experiment to PDF."""
    try:
        from utils.export_formats import export_experiment_pdf
    except ImportError as e:
        raise HTTPException(500, f"PDF 导出依赖缺失: {e}")
    try:
        filepath = export_experiment_pdf(exp_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return FileResponse(filepath, media_type="application/pdf",
                        filename=os.path.basename(filepath))


@router.get("/export/experiment/{exp_id}/docx")
def export_docx(exp_id: int):
    """Export a single experiment to Word (.docx)."""
    try:
        from utils.export_formats import export_experiment_docx
    except ImportError as e:
        raise HTTPException(500, f"Word 导出依赖缺失: {e}")
    try:
        filepath = export_experiment_docx(exp_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=os.path.basename(filepath))


@router.get("/export/experiments/excel")
def export_xls(ids: str = ""):
    """Export experiments to Excel. ids is comma-separated IDs or empty for all."""
    exp_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    filepath = export_experiments_excel(exp_ids)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(filepath))


@router.get("/export/all/json")
def export_json():
    data = export_all_json()
    return PlainTextResponse(
        data,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=chemeln_export.json"})


@router.get("/backup/database")
def backup_db():
    """Create a full SQLite backup."""
    filepath = backup_database()
    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=os.path.basename(filepath))


@router.get("/backup/settings")
def get_backup_settings():
    """自动备份配置 + 备份列表。"""
    from utils.auto_backup import get_settings, list_backups
    cfg = get_settings()
    cfg["backups"] = list_backups()
    return cfg


@router.put("/backup/settings")
def update_backup_settings(payload: dict):
    """更新自动备份配置（enabled / interval_hours / keep）。"""
    from utils.auto_backup import update_settings
    try:
        return update_settings(
            enabled=payload.get("enabled"),
            interval_hours=payload.get("interval_hours"),
            keep=payload.get("keep"),
        )
    except Exception as e:
        raise HTTPException(500, f"保存失败: {e}")


@router.post("/backup/run")
def run_backup_now():
    """立即执行一次备份（DB + 附件打包 zip），并按保留份数轮转。"""
    from utils.auto_backup import run_backup, prune_backups, get_settings
    try:
        info = run_backup("manual")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"备份失败: {e}")
    prune_backups(get_settings()["keep"])
    return info


@router.get("/backup/list")
def list_backup_files():
    from utils.auto_backup import list_backups
    return {"backups": list_backups()}


@router.get("/backup/download/{name}")
def download_backup(name: str):
    from utils.auto_backup import find_backup
    path = find_backup(name)
    if not path:
        raise HTTPException(404, "备份文件不存在")
    media = "application/zip" if path.endswith(".zip") else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=os.path.basename(path))


@router.post("/import/csv")
async def import_csv(file: UploadFile = File(...), table: str = "experiments"):
    """Import data from a CSV file."""
    # Save uploaded file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    content = await file.read()
    tmp.write(content)
    tmp.close()

    result = import_from_csv(tmp.name, table)
    os.unlink(tmp.name)
    return result


@router.post("/import/json")
async def import_json(file: UploadFile = File(...)):
    """Import from a previously exported JSON file."""
    import json
    content = await file.read()
    data = json.loads(content)

    db = get_db()
    imported = {"tables": {}}

    # Import each table
    table_order = ["compounds", "templates", "tags", "experiments",
                   "reagents", "experiment_tags", "attachments",
                   "experiment_links", "settings"]

    for table in table_order:
        rows = data.get(table, [])
        if not rows:
            continue

        count = 0
        for row in rows:
            cols = list(row.keys())
            vals = [row[c] for c in cols]
            placeholders = ",".join(["?"] * len(cols))
            col_str = ",".join(cols)
            try:
                db.execute(f"INSERT OR IGNORE INTO {table} ({col_str}) VALUES ({placeholders})", vals)
                count += 1
            except Exception:
                pass
        imported["tables"][table] = count

    db.commit()
    db.close()
    return imported


def _md_to_html(md: str) -> str:
    """Basic markdown to HTML conversion."""
    import re
    # Headers
    md = re.sub(r'^### (.+)$', r'<h3>\1</h3>', md, flags=re.M)
    md = re.sub(r'^## (.+)$', r'<h2>\1</h2>', md, flags=re.M)
    md = re.sub(r'^# (.+)$', r'<h1>\1</h1>', md, flags=re.M)
    # Bold
    md = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', md)
    # Code
    md = re.sub(r'`(.+?)`', r'<code>\1</code>', md)
    # Tables (basic)
    lines = md.split('\n')
    in_table = False
    result = []
    for line in lines:
        if '|' in line and line.strip().startswith('|'):
            if not in_table:
                result.append('<table border="1" cellpadding="5">')
                in_table = True
                continue  # skip header separator
            cells = [c.strip() for c in line.strip('|').split('|')]
            result.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
        else:
            if in_table:
                result.append('</table>')
                in_table = False
            if line.strip():
                result.append(f'<p>{line}</p>')
    if in_table:
        result.append('</table>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
h1,h2,h3 {{ color: #2c3e50; }}
table {{ border-collapse: collapse; width: 100%; }}
td {{ padding: 5px; }}
code {{ background: #f5f5f5; padding: 2px 4px; }}
</style></head><body>
{chr(10).join(result)}
</body></html>"""
