"""Templates router — reaction/workup/crystallization templates."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db
import json

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    type: str = "reaction"
    content: str = ""
    reagent_template: str = ""  # JSON string
    reaction_template: str = ""  # JSON string (reaction scheme)


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    reagent_template: Optional[str] = None
    reaction_template: Optional[str] = None


@router.get("")
def list_templates(type_filter: str = ""):
    db = get_db()
    if type_filter:
        rows = db.execute("SELECT * FROM templates WHERE type = ? ORDER BY name",
                           (type_filter,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM templates ORDER BY name").fetchall()
    db.close()
    return {"templates": [dict(r) for r in rows], "count": len(rows)}


@router.get("/{tid}")
def get_template(tid: int):
    db = get_db()
    row = db.execute("SELECT * FROM templates WHERE id = ?", (tid,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Template not found")
    return dict(row)


@router.post("")
def create_template(tpl: TemplateCreate):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO templates (name, type, content, reagent_template, reaction_template) VALUES (?, ?, ?, ?, ?)",
        (tpl.name, tpl.type, tpl.content, tpl.reagent_template, tpl.reaction_template))
    tid = cursor.lastrowid
    db.commit()
    db.close()
    return {"id": tid, "message": "Template created"}


@router.put("/{tid}")
def update_template(tid: int, tpl: TemplateUpdate):
    db = get_db()
    updates = []
    params = []
    for field, value in tpl.model_dump(exclude_none=True).items():
        updates.append(f"{field} = ?")
        params.append(value)

    if updates:
        params.append(tid)
        db.execute(f"UPDATE templates SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()

    db.close()
    return {"id": tid, "message": "Template updated"}


@router.delete("/{tid}")
def delete_template(tid: int):
    db = get_db()
    db.execute("DELETE FROM templates WHERE id = ?", (tid,))
    db.commit()
    db.close()
    return {"id": tid, "message": "Template deleted"}
