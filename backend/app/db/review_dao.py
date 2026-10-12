"""复习资料 DAO（P3）。返回纯 dict。"""
import json
from typing import Optional

from app.db.engine import get_db
from app.db.models.learning import ReviewMaterial
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _row_dict(row: ReviewMaterial, with_content: bool = False) -> dict:
    data = {
        "id": row.id,
        "collection_id": row.collection_id,
        "title": row.title or "",
        "detail_mode": row.detail_mode or "full",
        "status": row.status or "pending",
        "progress": row.progress or "",
        "error": row.error or "",
        "created_at": str(row.created_at or ""),
        "updated_at": str(row.updated_at or ""),
    }
    if with_content:
        content = {}
        if row.content_json:
            try:
                content = json.loads(row.content_json)
            except Exception:
                content = {}
        data["content"] = content
    return data


def create_material(collection_id: int, title: str = "", detail_mode: str = "full") -> dict:
    db = next(get_db())
    try:
        row = ReviewMaterial(
            collection_id=collection_id,
            title=title or "",
            detail_mode=detail_mode if detail_mode in ("full", "brief") else "full",
            status="pending",
            progress="排队中",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _row_dict(row)
    finally:
        db.close()


def update_progress(material_id: int, progress: str, status: str = "processing") -> None:
    db = next(get_db())
    try:
        row = db.query(ReviewMaterial).filter_by(id=material_id).first()
        if row:
            row.progress = progress
            row.status = status
            db.commit()
    finally:
        db.close()


def finalize_material(material_id: int, title: str, content: dict) -> Optional[dict]:
    db = next(get_db())
    try:
        row = db.query(ReviewMaterial).filter_by(id=material_id).first()
        if not row:
            return None
        row.title = title or row.title
        row.content_json = json.dumps(content, ensure_ascii=False)
        row.status = "done"
        row.progress = "完成"
        row.error = ""
        db.commit()
        db.refresh(row)
        return _row_dict(row, with_content=True)
    finally:
        db.close()


def fail_material(material_id: int, error: str) -> None:
    db = next(get_db())
    try:
        row = db.query(ReviewMaterial).filter_by(id=material_id).first()
        if row:
            row.status = "failed"
            row.error = error
            row.progress = "失败"
            db.commit()
    finally:
        db.close()


def get_material(material_id: int) -> Optional[dict]:
    db = next(get_db())
    try:
        row = db.query(ReviewMaterial).filter_by(id=material_id).first()
        return _row_dict(row, with_content=True) if row else None
    finally:
        db.close()


def list_materials(collection_id: Optional[int] = None) -> list:
    db = next(get_db())
    try:
        q = db.query(ReviewMaterial)
        if collection_id:
            q = q.filter_by(collection_id=collection_id)
        rows = q.order_by(ReviewMaterial.created_at.desc()).all()
        return [_row_dict(r) for r in rows]
    finally:
        db.close()


def delete_material(material_id: int) -> bool:
    db = next(get_db())
    try:
        row = db.query(ReviewMaterial).filter_by(id=material_id).first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()
