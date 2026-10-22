"""Experiments router — CRUD, tags, reagents, attachments, versions, links."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from database import get_db
from utils.fts import sync_experiment
import os, json, shutil

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class ExperimentCreate(BaseModel):
    title: str = "Untitled"
    content: str = ""
    project: str = ""
    status: str = "draft"
    exp_date: str = ""
    target_compound: str = ""
    yield_pct: Optional[float] = None
    purity_pct: Optional[float] = None
    notes: str = ""
    fk_compound_id: Optional[int] = None
    step_no: Optional[int] = None   # 合成路线中的第几步
    template_id: Optional[int] = None


class ExperimentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    project: Optional[str] = None
    status: Optional[str] = None
    exp_date: Optional[str] = None
    target_compound: Optional[str] = None
    yield_pct: Optional[float] = None
    purity_pct: Optional[float] = None
    notes: Optional[str] = None
    fk_compound_id: Optional[int] = None
    step_no: Optional[int] = None   # 合成路线中的第几步


@router.get("")
def list_experiments(
    q: str = "",
    project: str = "",
    status: str = "",
    tag: str = "",
    step: Optional[int] = None,
    min_yield: Optional[float] = None,
    max_yield: Optional[float] = None,
    min_purity: Optional[float] = None,
    max_purity: Optional[float] = None,
    sort: str = "updated_at",
    order: str = "desc",
    limit: int = 200,
    offset: int = 0,
):
    """List experiments with optional filters."""
    db = get_db()
    query = "SELECT DISTINCT e.* FROM experiments e"
    params = []
    joins = []
    conditions = []

    if tag:
        joins.append("JOIN experiment_tags et ON et.experiment_id = e.id JOIN tags t ON t.id = et.tag_id")
        conditions.append("t.name = ?")
        params.append(tag)

    if joins:
        query += " " + " ".join(joins)

    if q:
        conditions.append("(e.title LIKE ? OR e.content LIKE ? OR e.target_compound LIKE ? OR e.notes LIKE ?)")
        params.extend([f"%{q}%"] * 4)

    if project:
        conditions.append("e.project = ?")
        params.append(project)

    if status:
        conditions.append("e.status = ?")
        params.append(status)

    if step is not None:
        conditions.append("e.step_no = ?")
        params.append(step)

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

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # Valid sort columns
    valid_sorts = {"updated_at", "created_at", "title", "exp_date", "yield_pct", "purity_pct", "id"}
    sort = sort if sort in valid_sorts else "updated_at"
    order = "ASC" if order.upper() == "ASC" else "DESC"
    query += f" ORDER BY e.{sort} {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(query, params).fetchall()
    result = []
    for r in rows:
        exp = dict(r)
        # Fetch tags
        tags = db.execute(
            "SELECT t.id, t.name, t.color FROM tags t "
            "JOIN experiment_tags et ON t.id = et.tag_id "
            "WHERE et.experiment_id = ?", (exp["id"],)).fetchall()
        exp["tags"] = [dict(t) for t in tags]
        # Fetch reagent count
        rcount = db.execute(
            "SELECT COUNT(*) as c FROM reagents WHERE experiment_id = ?",
            (exp["id"],)).fetchone()
        exp["reagent_count"] = rcount["c"] if rcount else 0
        # Attachment count
        acount = db.execute(
            "SELECT COUNT(*) as c FROM attachments WHERE experiment_id = ?",
            (exp["id"],)).fetchone()
        exp["attachment_count"] = acount["c"] if acount else 0
        result.append(exp)

    db.close()
    return {"experiments": result, "count": len(result)}


@router.get("/{exp_id}")
def get_experiment(exp_id: int):
    """Get a single experiment with all related data."""
    db = get_db()
    exp = db.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()
    if not exp:
        db.close()
        raise HTTPException(404, "Experiment not found")

    result = dict(exp)

    # Tags
    tags = db.execute(
        "SELECT t.* FROM tags t JOIN experiment_tags et ON t.id = et.tag_id "
        "WHERE et.experiment_id = ?", (exp_id,)).fetchall()
    result["tags"] = [dict(t) for t in tags]

    # Reagents
    reagents = db.execute(
        "SELECT * FROM reagents WHERE experiment_id = ? ORDER BY sort_order",
        (exp_id,)).fetchall()
    result["reagents"] = [dict(r) for r in reagents]

    # Attachments
    attachments = db.execute(
        "SELECT * FROM attachments WHERE experiment_id = ?", (exp_id,)).fetchall()
    result["attachments"] = [dict(a) for a in attachments]

    # Compound
    if result.get("fk_compound_id"):
        compound = db.execute(
            "SELECT * FROM compounds WHERE id = ?",
            (result["fk_compound_id"],)).fetchone()
        result["compound"] = dict(compound) if compound else None
    else:
        result["compound"] = None

    # Reaction scheme
    reaction = db.execute(
        "SELECT * FROM reactions WHERE experiment_id = ? ORDER BY id DESC LIMIT 1",
        (exp_id,)).fetchone()
    if reaction:
        r = dict(reaction)
        try:
            r["reactant_smiles"] = json.loads(r["reactant_smiles"] or "[]")
            r["product_smiles"] = json.loads(r["product_smiles"] or "[]")
        except Exception:
            r["reactant_smiles"], r["product_smiles"] = [], []
        result["reaction"] = r
    else:
        result["reaction"] = None

    # Linked experiments
    links = db.execute(
        "SELECT el.*, e.title as linked_title FROM experiment_links el "
        "JOIN experiments e ON e.id = el.to_exp WHERE el.from_exp = ?",
        (exp_id,)).fetchall()
    result["links"] = [dict(l) for l in links]

    # Recent versions
    versions = db.execute(
        "SELECT id, version_note, created_at FROM versions "
        "WHERE experiment_id = ? ORDER BY created_at DESC LIMIT 20",
        (exp_id,)).fetchall()
    result["versions"] = [dict(v) for v in versions]

    db.close()
    return result


@router.post("")
def create_experiment(exp: ExperimentCreate):
    """Create a new experiment, optionally from a template."""
    db = get_db()

    content = exp.content
    reagent_template = None
    reaction_template = None

    # If template_id provided, load template content
    if exp.template_id:
        tpl = db.execute("SELECT * FROM templates WHERE id = ?",
                          (exp.template_id,)).fetchone()
        if tpl:
            if not content:
                content = tpl["content"]
            reagent_template = tpl["reagent_template"]
            reaction_template = tpl["reaction_template"]

    cursor = db.execute(
        """INSERT INTO experiments
           (title, content, project, status, exp_date, target_compound,
            yield_pct, purity_pct, notes, fk_compound_id, step_no)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (exp.title, content, exp.project, exp.status, exp.exp_date,
         exp.target_compound, exp.yield_pct, exp.purity_pct, exp.notes,
         exp.fk_compound_id, exp.step_no))
    exp_id = cursor.lastrowid
    sync_experiment(db, exp_id)

    # Create reagents from template if available
    if reagent_template:
        try:
            reagents = json.loads(reagent_template) if isinstance(reagent_template, str) else reagent_template
            for i, r in enumerate(reagents):
                rt = r.get("ratio_type", "equiv")
                rv = r.get("ratio_value")
                if rv is None:
                    rv = r.get("equivalents", 0)
                mg = r.get("mass_g")
                if mg is None and r.get("mass_mg") is not None:
                    mg = r.get("mass_mg") / 1000.0
                db.execute(
                    """INSERT INTO reagents
                       (experiment_id, role, name, ratio_type, ratio_value,
                        equivalents, mass_g, mw, smiles, sort_order,
                        density, concentration, purity_pct)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (exp_id, r.get("role", "reagent"), r.get("name", ""),
                     rt, rv, rv if rt == "equiv" else None,
                     mg, r.get("mw"), r.get("smiles", ""), i,
                     r.get("density"), r.get("concentration"), r.get("purity_pct")))
        except (json.JSONDecodeError, TypeError):
            pass

    # Create reaction from template if available
    if reaction_template:
        try:
            rxn = json.loads(reaction_template) if isinstance(reaction_template, str) else reaction_template
            if rxn:
                db.execute(
                    """INSERT INTO reactions
                       (experiment_id, display_mode, reactant_smiles, product_smiles,
                        conditions, arrow_label, image_path, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (exp_id, rxn.get("display_mode", "scheme"),
                     json.dumps(rxn.get("reactant_smiles", [])),
                     json.dumps(rxn.get("product_smiles", [])),
                     rxn.get("conditions", ""), rxn.get("arrow_label", ""),
                     rxn.get("image_path", ""), rxn.get("notes", "")))
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    db.commit()
    db.close()
    return {"id": exp_id, "message": "Experiment created"}


@router.put("/{exp_id}")
def update_experiment(exp_id: int, exp: ExperimentUpdate):
    """Update an experiment. Saves old version automatically."""
    db = get_db()
    old = db.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()
    if not old:
        db.close()
        raise HTTPException(404, "Experiment not found")

    # Save version snapshot
    db.execute(
        """INSERT INTO versions (experiment_id, content, reagents_json, version_note)
           VALUES (?, ?, ?, ?)""",
        (exp_id, old["content"], json.dumps([]), f"Auto-saved before update"))

    # Build update query dynamically
    updates = []
    params = []
    data = exp.model_dump(exclude_none=True)
    # step_no may be explicitly set to null (user cleared the field) → allow clearing
    if "step_no" in exp.model_fields_set and exp.step_no is None:
        data["step_no"] = None
    for field, value in data.items():
        updates.append(f"{field} = ?")
        params.append(value)

    if updates:
        updates.append("updated_at = datetime('now','localtime')")
        params.append(exp_id)
        db.execute(f"UPDATE experiments SET {', '.join(updates)} WHERE id = ?", params)

    sync_experiment(db, exp_id)
    db.commit()
    db.close()
    return {"id": exp_id, "message": "Experiment updated"}


@router.delete("/{exp_id}")
def delete_experiment(exp_id: int):
    """Delete an experiment and its related data."""
    db = get_db()
    # Delete attachments files
    atts = db.execute("SELECT file_path FROM attachments WHERE experiment_id = ?",
                       (exp_id,)).fetchall()
    for a in atts:
        full = os.path.join(ATTACH_DIR, a["file_path"])
        if os.path.exists(full):
            try:
                os.remove(full)
            except Exception:
                pass

    db.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))
    sync_experiment(db, exp_id)
    db.commit()
    db.close()
    return {"id": exp_id, "message": "Experiment deleted"}


# --- Tags ---

@router.post("/{exp_id}/tags/{tag_id}")
def add_tag(exp_id: int, tag_id: int):
    db = get_db()
    try:
        db.execute("INSERT INTO experiment_tags (experiment_id, tag_id) VALUES (?, ?)",
                    (exp_id, tag_id))
        db.commit()
    except Exception:
        pass
    db.close()
    return {"message": "Tag added"}


@router.delete("/{exp_id}/tags/{tag_id}")
def remove_tag(exp_id: int, tag_id: int):
    db = get_db()
    db.execute("DELETE FROM experiment_tags WHERE experiment_id = ? AND tag_id = ?",
                (exp_id, tag_id))
    db.commit()
    db.close()
    return {"message": "Tag removed"}


# --- Reagents ---

class ReagentItem(BaseModel):
    role: str = "reagent"
    compound_id: Optional[int] = None
    name: str = ""
    smiles: str = ""
    mw: Optional[float] = None
    # Stoichiometry: choose between equivalent ratio and weight ratio (relative to substrate)
    ratio_type: Optional[str] = "equiv"   # 'equiv' | 'weight'
    ratio_value: Optional[float] = None    # eq value, or weight ratio vs substrate mass
    equivalents: Optional[float] = None     # legacy / kept in sync for equiv mode
    mass_g: Optional[float] = None          # feeding mass in grams
    mass_mg: Optional[float] = None         # legacy
    moles_mmol: Optional[float] = None
    volume_ml: Optional[float] = None
    density: Optional[float] = None
    concentration: Optional[float] = None
    purity_pct: Optional[float] = None
    sort_order: int = 0


@router.put("/{exp_id}/reagents")
def update_reagents(exp_id: int, reagents: list[ReagentItem]):
    """Replace all reagents for an experiment."""
    db = get_db()
    # Save current reagents to version
    old_reagents = db.execute(
        "SELECT * FROM reagents WHERE experiment_id = ?", (exp_id,)).fetchall()
    if old_reagents:
        db.execute(
            """INSERT INTO versions (experiment_id, content, reagents_json, version_note)
               VALUES (?, '', ?, ?)""",
            (exp_id, json.dumps([dict(r) for r in old_reagents]), "Reagent table update"))

    db.execute("DELETE FROM reagents WHERE experiment_id = ?", (exp_id,))
    for r in reagents:
        # Keep `equivalents` in sync for equiv mode (legacy consumers)
        eq = r.equivalents
        if r.ratio_type == "equiv" and r.ratio_value is not None:
            eq = r.ratio_value
        db.execute(
            """INSERT INTO reagents
               (experiment_id, role, compound_id, name, smiles, mw, ratio_type, ratio_value,
                equivalents, mass_g, mass_mg, moles_mmol, volume_ml, density,
                concentration, purity_pct, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (exp_id, r.role, r.compound_id, r.name, r.smiles, r.mw, r.ratio_type,
             r.ratio_value, eq, r.mass_g, r.mass_mg, r.moles_mmol, r.volume_ml,
             r.density, r.concentration, r.purity_pct, r.sort_order))

    db.commit()
    db.close()
    return {"message": "Reagents updated", "count": len(reagents)}


@router.post("/{exp_id}/calculate-reagents")
def calculate_reagents(exp_id: int, data: dict):
    """Auto-calculate reagent table from substrate mass and equivalents."""
    from utils.chem import calculate_reagent_table

    substrate_mass = data.get("substrate_mass_mg", 0)
    substrate_mw = data.get("substrate_mw", 0)
    reagents = data.get("reagents", [])

    result = calculate_reagent_table(substrate_mass, substrate_mw, reagents)
    return {"reagents": result}


# --- Reaction scheme ---

class ReactionData(BaseModel):
    display_mode: str = "scheme"        # scheme | image
    reactant_smiles: list = []
    product_smiles: list = []
    conditions: str = ""
    arrow_label: str = ""
    image_path: str = ""
    notes: str = ""


@router.get("/{exp_id}/reaction")
def get_reaction(exp_id: int):
    """Get the reaction scheme for an experiment (one per experiment)."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM reactions WHERE experiment_id = ? ORDER BY id DESC LIMIT 1",
        (exp_id,)).fetchone()
    db.close()
    if not row:
        return {"reaction": None}
    r = dict(row)
    try:
        r["reactant_smiles"] = json.loads(r["reactant_smiles"] or "[]")
        r["product_smiles"] = json.loads(r["product_smiles"] or "[]")
    except Exception:
        r["reactant_smiles"], r["product_smiles"] = [], []
    return {"reaction": r}


@router.put("/{exp_id}/reaction")
def upsert_reaction(exp_id: int, data: ReactionData):
    """Create or update the reaction scheme for an experiment."""
    db = get_db()
    existing = db.execute(
        "SELECT id FROM reactions WHERE experiment_id = ? ORDER BY id DESC LIMIT 1",
        (exp_id,)).fetchone()

    reactants = json.dumps(data.reactant_smiles or [])
    products = json.dumps(data.product_smiles or [])

    if existing:
        db.execute(
            """UPDATE reactions SET display_mode=?, reactant_smiles=?, product_smiles=?,
               conditions=?, arrow_label=?, image_path=?, notes=?
               WHERE id=?""",
            (data.display_mode, reactants, products, data.conditions,
             data.arrow_label, data.image_path, data.notes, existing["id"]))
        rid = existing["id"]
    else:
        cursor = db.execute(
            """INSERT INTO reactions
               (experiment_id, display_mode, reactant_smiles, product_smiles,
                conditions, arrow_label, image_path, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (exp_id, data.display_mode, reactants, products, data.conditions,
             data.arrow_label, data.image_path, data.notes))
        rid = cursor.lastrowid
    db.commit()
    db.close()
    return {"message": "Reaction saved", "id": rid}


@router.post("/{exp_id}/reaction-image")
async def upload_reaction_image(exp_id: int, file: UploadFile = File(...)):
    """Upload a ChemDraw (or any) reaction image for the experiment."""
    db = get_db()
    exp = db.execute("SELECT id FROM experiments WHERE id = ?", (exp_id,)).fetchone()
    if not exp:
        db.close()
        raise HTTPException(404, "Experiment not found")

    exp_dir = os.path.join(ATTACH_DIR, str(exp_id))
    os.makedirs(exp_dir, exist_ok=True)

    filename = file.filename or "reaction.png"
    filename = os.path.basename(filename)
    # Unique-ish name to avoid collision
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = ".png"
    filename = f"reaction_{int(__import__('time').time()*1000)}{ext}"
    file_path = os.path.join(exp_dir, filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())
    rel_path = os.path.join(str(exp_id), filename)

    db.close()
    return {
        "image_path": rel_path,
        "url": f"/attachments/{rel_path.replace(os.sep, '/')}",
    }


# --- Attachments ---

@router.post("/{exp_id}/attachments")
async def upload_attachment(exp_id: int, file: UploadFile = File(...),
                             description: str = Form(""), file_type: str = Form("")):
    db = get_db()
    # Ensure experiment exists
    exp = db.execute("SELECT id FROM experiments WHERE id = ?", (exp_id,)).fetchone()
    if not exp:
        db.close()
        raise HTTPException(404, "Experiment not found")

    # Save file
    exp_dir = os.path.join(ATTACH_DIR, str(exp_id))
    os.makedirs(exp_dir, exist_ok=True)

    filename = file.filename or "unnamed"
    # Prevent path traversal
    filename = os.path.basename(filename)
    file_path = os.path.join(exp_dir, filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    file_size = os.path.getsize(file_path)

    # Auto-detect type
    if not file_type:
        ext = os.path.splitext(filename)[1].lower()
        type_map = {
            ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
            ".pdf": "pdf", ".csv": "data", ".txt": "data",
            ".hplc": "hplc", ".nmr": "nmr", ".fid": "nmr",
            ".zip": "archive",
        }
        file_type = type_map.get(ext, "other")

    cursor = db.execute(
        """INSERT INTO attachments
           (experiment_id, filename, file_path, file_type, file_size, description)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (exp_id, filename, os.path.join(str(exp_id), filename),
         file_type, file_size, description))
    att_id = cursor.lastrowid
    db.commit()
    db.close()
    return {"id": att_id, "filename": filename, "file_type": file_type, "file_size": file_size}


@router.delete("/{exp_id}/attachments/{att_id}")
def delete_attachment(exp_id: int, att_id: int):
    db = get_db()
    att = db.execute("SELECT * FROM attachments WHERE id = ? AND experiment_id = ?",
                      (att_id, exp_id)).fetchone()
    if not att:
        db.close()
        raise HTTPException(404, "Attachment not found")

    full = os.path.join(ATTACH_DIR, att["file_path"])
    if os.path.exists(full):
        try:
            os.remove(full)
        except Exception:
            pass

    db.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
    db.commit()
    db.close()
    return {"message": "Attachment deleted"}


# --- Versions ---

@router.get("/{exp_id}/versions/{ver_id}")
def get_version(exp_id: int, ver_id: int):
    db = get_db()
    ver = db.execute(
        "SELECT * FROM versions WHERE id = ? AND experiment_id = ?",
        (ver_id, exp_id)).fetchone()
    db.close()
    if not ver:
        raise HTTPException(404, "Version not found")
    return dict(ver)


@router.post("/{exp_id}/versions/{ver_id}/restore")
def restore_version(exp_id: int, ver_id: int):
    """Restore an experiment to a previous version."""
    db = get_db()
    ver = db.execute(
        "SELECT * FROM versions WHERE id = ? AND experiment_id = ?",
        (ver_id, exp_id)).fetchone()
    if not ver:
        db.close()
        raise HTTPException(404, "Version not found")

    # Save current state as a version first
    current = db.execute("SELECT content FROM experiments WHERE id = ?", (exp_id,)).fetchone()
    if current:
        db.execute(
            "INSERT INTO versions (experiment_id, content, reagents_json, version_note) VALUES (?, ?, ?, ?)",
            (exp_id, current["content"], "[]", "Pre-restore snapshot"))

    # Restore content
    db.execute("UPDATE experiments SET content = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (ver["content"], exp_id))
    db.commit()
    db.close()
    return {"message": "Version restored"}


# --- Links ---

@router.post("/{exp_id}/links/{to_exp}")
def add_link(exp_id: int, to_exp: int, link_type: str = "related"):
    db = get_db()
    try:
        db.execute(
            "INSERT INTO experiment_links (from_exp, to_exp, link_type) VALUES (?, ?, ?)",
            (exp_id, to_exp, link_type))
        db.commit()
    except Exception:
        pass
    db.close()
    return {"message": "Link added"}


@router.delete("/{exp_id}/links/{to_exp}")
def remove_link(exp_id: int, to_exp: int, link_type: str = "related"):
    db = get_db()
    db.execute(
        "DELETE FROM experiment_links WHERE from_exp = ? AND to_exp = ? AND link_type = ?",
        (exp_id, to_exp, link_type))
    db.commit()
    db.close()
    return {"message": "Link removed"}
