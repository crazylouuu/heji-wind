"""Compounds & cheminformatics router."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from utils.fts import sync_compound
from config import BACKUP_DIR
from utils.chem import (parse_smiles, parse_molfile, render_structure_image,
                        substructure_search, get_molblock, smiles_to_inchikey)
from utils.common_reagents import lookup_common_reagent

router = APIRouter(prefix="/api/compounds", tags=["compounds"])


class CompoundCreate(BaseModel):
    name: str = ""
    cas: str = ""
    smiles: str = ""
    molfile: str = ""
    inchi: str = ""
    notes: str = ""
    category: str = "project"   # solvent|reagent|project


class CompoundUpdate(BaseModel):
    name: Optional[str] = None
    cas: Optional[str] = None
    smiles: Optional[str] = None
    molfile: Optional[str] = None
    inchi: Optional[str] = None
    inchikey: Optional[str] = None
    mw: Optional[float] = None
    formula: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None


@router.get("")
def list_compounds(q: str = "", category: str = "", limit: int = 2000):
    db = get_db()
    sql = "SELECT * FROM compounds"
    params = []
    where = []
    if q:
        where.append("(name LIKE ? OR cas LIKE ? OR smiles LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if category and category != "all":
        where.append("category = ?")
        params.append(category)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    rows = db.execute(sql, params).fetchall()
    db.close()
    return {"compounds": [dict(r) for r in rows], "count": len(rows)}


@router.get("/export-excel")
def export_compounds_excel():
    """Export the whole compound library to an Excel file."""
    import os
    from datetime import datetime
    import openpyxl

    db = get_db()
    rows = db.execute(
        "SELECT name,cas,smiles,inchi,inchikey,formula,mw,notes,category "
        "FROM compounds ORDER BY name").fetchall()
    db.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "化合物库"
    headers = ["名称", "CAS", "SMILES", "InChI", "InChIKey", "分子式", "分子量", "备注", "分类"]
    ws.append(headers)
    for r in rows:
        cat_label = {"solvent": "溶剂", "reagent": "试剂", "project": "项目"}.get(r["category"], r["category"] or "")
        ws.append([
            r["name"], r["cas"] or "", r["smiles"] or "", r["inchi"] or "",
            r["inchikey"] or "", r["formula"] or "",
            r["mw"] if r["mw"] is not None else "",
            r["notes"] or "",
            cat_label,
        ])
    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    filepath = os.path.join(BACKUP_DIR, f"compounds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    wb.save(filepath)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(filepath))


@router.get("/{cid}")
def get_compound(cid: int):
    db = get_db()
    row = db.execute("SELECT * FROM compounds WHERE id = ?", (cid,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Compound not found")
    return dict(row)


@router.post("")
def create_compound(comp: CompoundCreate):
    db = get_db()
    # Auto-fill chemical info from SMILES or molfile
    info = {}
    if comp.smiles:
        info = parse_smiles(comp.smiles)
    elif comp.molfile:
        info = parse_molfile(comp.molfile)

    smiles = comp.smiles or info.get("smiles", "")
    inchi = comp.inchi or info.get("inchi", "")
    inchikey = info.get("inchikey", "")
    mw = info.get("mw")
    formula = info.get("formula")

    # Check for duplicates by InChIKey (same molecular structure)
    if inchikey:
        existing = db.execute(
            "SELECT id, name, cas, category FROM compounds WHERE inchikey = ?", (inchikey,)).fetchone()
        if existing:
            db.close()
            return {
                "id": existing["id"],
                "duplicate": True,
                "reason": "inchikey",
                "message": "Duplicate compound (same InChIKey)",
                "existing": dict(existing),
            }

    # Check for exact same name (prevents structure-less duplicates piling up)
    if comp.name:
        same_name = db.execute(
            "SELECT id, name, cas, category FROM compounds WHERE name = ?", (comp.name,)).fetchone()
        if same_name:
            db.close()
            return {
                "id": same_name["id"],
                "duplicate": True,
                "reason": "name",
                "message": "Duplicate compound (same name)",
                "existing": dict(same_name),
            }

    cursor = db.execute(
        """INSERT INTO compounds
           (name, cas, smiles, inchi, inchikey, molfile, mw, formula, notes, category)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (comp.name, comp.cas, smiles, inchi, inchikey,
         comp.molfile, mw, formula, comp.notes, comp.category))
    cid = cursor.lastrowid
    sync_compound(db, cid)
    db.commit()
    db.close()
    return {"id": cid, "message": "Compound created", "info": info}


@router.put("/{cid}")
def update_compound(cid: int, comp: CompoundUpdate):
    db = get_db()
    old = db.execute("SELECT * FROM compounds WHERE id = ?", (cid,)).fetchone()
    if not old:
        db.close()
        raise HTTPException(404, "Compound not found")

    updates = []
    params = []
    for field, value in comp.model_dump(exclude_none=True).items():
        updates.append(f"{field} = ?")
        params.append(value)

    if updates:
        params.append(cid)
        db.execute(f"UPDATE compounds SET {', '.join(updates)} WHERE id = ?", params)

    sync_compound(db, cid)
    db.commit()
    db.close()
    return {"id": cid, "message": "Compound updated"}


@router.delete("/{cid}")
def delete_compound(cid: int):
    db = get_db()
    db.execute("DELETE FROM compounds WHERE id = ?", (cid,))
    sync_compound(db, cid)
    db.commit()
    db.close()
    return {"id": cid, "message": "Compound deleted"}


# --- Bulk operations: Excel import & batch delete ---

@router.post("/import-excel")
async def import_compounds_excel(file: UploadFile = File(...), default_category: str = Form("project")):
    """Import compounds from an Excel (.xlsx) file. Supports Chinese/English headers.

    Expected columns (any subset): name/名称, cas, smiles, molfile/mol, inchi, notes/备注.
    Rows with an empty name are skipped. Duplicates (same InChIKey or same name) are skipped.
    """
    import io
    import openpyxl
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    except Exception as e:
        raise HTTPException(400, f"无法解析Excel文件: {e}")
    ws = wb.active
    grid = list(ws.iter_rows(values_only=True))
    if not grid:
        return {"imported": 0, "skipped": 0, "errors": 0, "message": "文件为空"}

    # Build header -> canonical field map (support CN/EN aliases)
    header = [(str(h).strip().lower() if h is not None else "") for h in grid[0]]
    aliases = {
        "name": ["name", "名称", "化合物名称", "化合物", "compound"],
        "cas": ["cas", "cas号", "casno"],
        "smiles": ["smiles", "smile", "结构式"],
        "molfile": ["molfile", "mol", "mol块", "molblock", "结构"],
        "inchi": ["inchi"],
        "notes": ["notes", "备注", "注释", "remark"],
        "category": ["category", "分类", "类别"],
    }
    field_index = {}
    for field, alist in aliases.items():
        for i, h in enumerate(header):
            if h in alist:
                field_index[field] = i
                break

    if "name" not in field_index:
        raise HTTPException(400, "Excel缺少必需的'名称/name'列")

    # Map a raw category label to internal code.
    # If the row has no category specified, fall back to the caller's
    # default_category (e.g. the tab the user imported from), not hard-coded "project".
    default_category = default_category if default_category in ("solvent", "reagent", "project") else "project"

    def norm_category(raw):
        if not raw:
            return default_category
        r = raw.strip().lower()
        if r in ("solvent", "溶剂", "溶媒"):
            return "solvent"
        if r in ("reagent", "试剂", "反应物"):
            return "reagent"
        if r in ("project", "项目", "项目化合物"):
            return "project"
        return default_category

    db = get_db()
    imported = skipped = errors = 0
    for row in grid[1:]:
        def get(field):
            idx = field_index.get(field)
            if idx is None or idx >= len(row) or row[idx] is None:
                return ""
            return str(row[idx]).strip()
        name = get("name")
        if not name:
            errors += 1
            continue
        cas = get("cas")
        smiles = get("smiles")
        molfile = get("molfile")
        inchi = get("inchi")
        notes = get("notes")
        category = norm_category(get("category"))

        # Auto-fill chemical info from SMILES/molfile, same as create_compound
        info = {}
        if smiles:
            info = parse_smiles(smiles)
        elif molfile:
            info = parse_molfile(molfile)
        smi = smiles or info.get("smiles", "")
        inc = inchi or info.get("inchi", "")
        ik = info.get("inchikey", "")
        mw = info.get("mw")
        formula = info.get("formula")

        # Dedup by InChIKey, then by name (case-insensitive)
        dup = False
        if ik:
            if db.execute("SELECT 1 FROM compounds WHERE inchikey=?", (ik,)).fetchone():
                dup = True
        if not dup and name:
            if db.execute("SELECT 1 FROM compounds WHERE name=? COLLATE NOCASE", (name,)).fetchone():
                dup = True
        if dup:
            skipped += 1
            continue

        db.execute(
            "INSERT INTO compounds (name,cas,smiles,inchi,inchikey,molfile,mw,formula,notes,category) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (name, cas, smi, inc, ik, molfile, mw, formula, notes, category))
        imported += 1

    db.commit()
    db.close()
    return {"imported": imported, "skipped": skipped, "errors": errors,
            "message": f"导入 {imported} 条，跳过重复 {skipped} 条，忽略空行 {errors} 条"}


class BatchDeleteReq(BaseModel):
    ids: List[int]


@router.post("/batch-delete")
def batch_delete_compounds(body: BatchDeleteReq):
    """Delete multiple compounds by id list."""
    if not body.ids:
        return {"deleted": 0}
    placeholders = ",".join("?" * len(body.ids))
    db = get_db()
    db.execute(f"DELETE FROM compounds WHERE id IN ({placeholders})", body.ids)
    db.commit()
    db.close()
    return {"deleted": len(body.ids)}


# --- Cheminformatics endpoints ---

@router.post("/parse-smiles")
def api_parse_smiles(data: dict):
    """Parse SMILES and return molecular info."""
    smiles = data.get("smiles", "")
    info = parse_smiles(smiles)
    if info.get("valid"):
        info["image"] = render_structure_image(smiles)
    return info


@router.post("/parse-molfile")
def api_parse_molfile(data: dict):
    """Parse a mol block and return molecular info."""
    molfile = data.get("molfile", "")
    info = parse_molfile(molfile)
    if info.get("valid"):
        info["image"] = render_structure_image(info["smiles"])
    return info


@router.post("/render")
def api_render_structure(data: dict):
    """Render a structure image from SMILES."""
    smiles = data.get("smiles", "")
    img = render_structure_image(smiles)
    if img:
        return {"image": f"data:image/png;base64,{img}"}
    return {"image": "", "error": "Cannot render structure"}


@router.post("/substructure-search")
def api_substructure_search(data: dict):
    """Search all compounds for a substructure match."""
    query_smiles = data.get("smiles", "")
    if not query_smiles:
        # Search in experiments
        db = get_db()
        rows = db.execute("SELECT id, name, smiles FROM compounds WHERE smiles != ''").fetchall()
        db.close()
        return {"matches": [], "count": 0}

    db = get_db()
    rows = db.execute("SELECT * FROM compounds WHERE smiles != ''").fetchall()
    matches = []
    for r in rows:
        if substructure_search(r["smiles"], query_smiles):
            matches.append(dict(r))
    db.close()
    return {"matches": matches, "count": len(matches)}


@router.post("/to-molblock")
def api_to_molblock(data: dict):
    """Convert SMILES to mol block."""
    smiles = data.get("smiles", "")
    molblock = get_molblock(smiles)
    return {"molblock": molblock}


def _lookup_hit(row, source: str, db):
    """Build a standard lookup response from a library row and close the db."""
    resp = {
        "found": True,
        "source": source,
        "compound_id": row["id"],
        "name": row["name"],
        "mw": row["mw"],
        "smiles": row["smiles"] or "",
        "formula": row["formula"] or "",
        "cas": row["cas"] or "",
    }
    db.close()
    return resp


@router.post("/lookup-mw")
def api_lookup_mw(data: dict):
    """
    Look up a compound from the library by name, CAS number, or SMILES.
    Returns molecular weight and related info in one call.
    """
    query = (data.get("name") or "").strip()
    if not query:
        return {"found": False}

    db = get_db()

    # 1. Exact name match (case-insensitive)
    row = db.execute(
        "SELECT * FROM compounds WHERE name = ? COLLATE NOCASE", (query,)
    ).fetchone()

    # 2. Exact CAS match (hyphens normalized: 100447 == 100-44-7)
    if not row:
        cas_norm = query.replace("-", "")
        if len(cas_norm) >= 4 and cas_norm.isdigit():
            row = db.execute(
                "SELECT * FROM compounds WHERE REPLACE(cas,'-','') = ? "
                "COLLATE NOCASE ORDER BY id LIMIT 1",
                (cas_norm,),
            ).fetchone()
            if row:
                return _lookup_hit(row, source="cas", db=db)

    # 3. Try parsing the input as a SMILES string, then reverse-lookup
    #    the library by InChIKey so the standard library name is shown.
    if not row:
        info = parse_smiles(query)
        if info.get("valid"):
            if info.get("inchikey"):
                hit = db.execute(
                    "SELECT * FROM compounds WHERE inchikey = ? ORDER BY id LIMIT 1",
                    (info["inchikey"],),
                ).fetchone()
                if hit:
                    return _lookup_hit(hit, source="smiles", db=db)
            db.close()
            return {
                "found": True,
                "source": "smiles",
                "name": query,
                "mw": info["mw"],
                "smiles": info["smiles"],
                "formula": info["formula"] or "",
                "inchikey": info.get("inchikey", ""),
            }

    # 4. Partial name match if no exact hit
    if not row:
        row = db.execute(
            "SELECT * FROM compounds WHERE name LIKE ? COLLATE NOCASE "
            "OR cas LIKE ? COLLATE NOCASE "
            "OR smiles = ? COLLATE NOCASE "
            "ORDER BY name LIMIT 1",
            (f"%{query}%", f"%{query}%", query)
        ).fetchone()

    if row:
        return _lookup_hit(row, source="library", db=db)

    db.close()

    # 5. Built-in common reagent dictionary (Chinese/English names, abbreviations, formulas)
    common = lookup_common_reagent(query)
    if common:
        return {
            "found": True,
            "source": common["source"],  # "common" or "formula"
            "name": common["name"],
            "mw": common["mw"],
            "formula": common["formula"],
            "cas": common.get("cas", ""),
        }

    return {"found": False, "name": query}
