"""合集/课程 DAO。返回纯 dict，避免 ORM 对象在 session 关闭后失效。"""
from typing import Optional

from app.db.engine import get_db
from app.db.models.learning import Collection, CollectionItem
from app.utils.logger import get_logger

logger = get_logger(__name__)

VALID_LEARNING_STATUS = ("unlearned", "learning", "completed")


def _collection_dict(row: Collection) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description or "",
        "created_at": str(row.created_at or ""),
        "updated_at": str(row.updated_at or ""),
    }


def _item_dict(row: CollectionItem) -> dict:
    return {
        "id": row.id,
        "collection_id": row.collection_id,
        "task_id": row.task_id,
        "video_id": row.video_id or "",
        "platform": row.platform or "",
        "sort_order": row.sort_order or 0,
        "learning_status": row.learning_status or "unlearned",
        "created_at": str(row.created_at or ""),
    }


def create_collection(name: str, description: str = "") -> dict:
    db = next(get_db())
    try:
        row = Collection(name=name, description=description or "")
        db.add(row)
        db.commit()
        db.refresh(row)
        return _collection_dict(row)
    finally:
        db.close()


def get_collection(collection_id: int) -> Optional[dict]:
    db = next(get_db())
    try:
        row = db.query(Collection).filter_by(id=collection_id).first()
        return _collection_dict(row) if row else None
    finally:
        db.close()


def list_collections() -> list:
    """合集列表（含条目数与学习进度统计）。"""
    db = next(get_db())
    try:
        result = []
        for row in db.query(Collection).order_by(Collection.created_at.desc()).all():
            items = db.query(CollectionItem).filter_by(collection_id=row.id).all()
            statuses = [i.learning_status or "unlearned" for i in items]
            data = _collection_dict(row)
            data["item_count"] = len(items)
            data["completed_count"] = statuses.count("completed")
            data["learning_count"] = statuses.count("learning")
            result.append(data)
        return result
    finally:
        db.close()


def update_collection(collection_id: int, name: Optional[str] = None,
                      description: Optional[str] = None) -> Optional[dict]:
    db = next(get_db())
    try:
        row = db.query(Collection).filter_by(id=collection_id).first()
        if not row:
            return None
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        db.commit()
        db.refresh(row)
        return _collection_dict(row)
    finally:
        db.close()


def delete_collection(collection_id: int) -> bool:
    """删除合集及其条目（不删除笔记任务本身）。"""
    db = next(get_db())
    try:
        row = db.query(Collection).filter_by(id=collection_id).first()
        if not row:
            return False
        db.query(CollectionItem).filter_by(collection_id=collection_id).delete()
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def add_item(collection_id: int, task_id: str, video_id: str = "",
             platform: str = "", sort_order: Optional[int] = None) -> Optional[dict]:
    """把笔记任务加入合集；同合集内 task_id 去重，已存在则直接返回旧条目。"""
    db = next(get_db())
    try:
        if not db.query(Collection).filter_by(id=collection_id).first():
            return None
        existing = db.query(CollectionItem).filter_by(
            collection_id=collection_id, task_id=task_id
        ).first()
        if existing:
            return _item_dict(existing)
        if sort_order is None:
            max_order = (db.query(CollectionItem)
                         .filter_by(collection_id=collection_id)
                         .order_by(CollectionItem.sort_order.desc())
                         .first())
            sort_order = (max_order.sort_order + 1) if max_order else 0
        row = CollectionItem(
            collection_id=collection_id,
            task_id=task_id,
            video_id=video_id or "",
            platform=platform or "",
            sort_order=sort_order,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _item_dict(row)
    finally:
        db.close()


def remove_item(collection_id: int, item_id: int) -> bool:
    db = next(get_db())
    try:
        row = db.query(CollectionItem).filter_by(
            id=item_id, collection_id=collection_id
        ).first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def list_items(collection_id: int) -> list:
    db = next(get_db())
    try:
        rows = (db.query(CollectionItem)
                .filter_by(collection_id=collection_id)
                .order_by(CollectionItem.sort_order.asc())
                .all())
        return [_item_dict(r) for r in rows]
    finally:
        db.close()


def update_item_status(item_id: int, learning_status: str) -> Optional[dict]:
    if learning_status not in VALID_LEARNING_STATUS:
        raise ValueError(f"非法学习状态: {learning_status}（可选 {VALID_LEARNING_STATUS}）")
    db = next(get_db())
    try:
        row = db.query(CollectionItem).filter_by(id=item_id).first()
        if not row:
            return None
        row.learning_status = learning_status
        db.commit()
        db.refresh(row)
        return _item_dict(row)
    finally:
        db.close()
