"""合集/课程管理接口（P2）。

合集是学习闭环的组织单元：笔记任务归入合集 → 学习状态按合集统计 → P3 复习资料按合集生成。
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import collection_dao
from app.utils.response import ResponseWrapper as R

router = APIRouter(prefix="/collection", tags=["collection"])


class CollectionCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class CollectionUpdateRequest(BaseModel):
    id: int
    name: Optional[str] = None
    description: Optional[str] = None


class ItemAddRequest(BaseModel):
    task_id: str
    video_id: Optional[str] = ""
    platform: Optional[str] = ""
    sort_order: Optional[int] = None


class ItemStatusRequest(BaseModel):
    learning_status: str


@router.post("/create")
def create_collection(data: CollectionCreateRequest):
    if not (data.name or "").strip():
        return R.error("合集名称不能为空", code=400)
    return R.success(data=collection_dao.create_collection(data.name.strip(), data.description or ""))


@router.get("/list")
def list_collections():
    return R.success(data=collection_dao.list_collections())


@router.get("/detail/{collection_id}")
def get_collection(collection_id: int):
    collection = collection_dao.get_collection(collection_id)
    if not collection:
        return R.error("合集不存在", code=404)
    items = collection_dao.list_items(collection_id)
    statuses = [i["learning_status"] for i in items]
    collection["items"] = items
    collection["item_count"] = len(items)
    collection["completed_count"] = statuses.count("completed")
    collection["learning_count"] = statuses.count("learning")
    return R.success(data=collection)


@router.post("/update")
def update_collection(data: CollectionUpdateRequest):
    updated = collection_dao.update_collection(data.id, data.name, data.description)
    if not updated:
        return R.error("合集不存在", code=404)
    return R.success(data=updated)


@router.delete("/{collection_id}")
def delete_collection(collection_id: int):
    if not collection_dao.delete_collection(collection_id):
        return R.error("合集不存在", code=404)
    return R.success(data={"deleted": collection_id})


@router.post("/{collection_id}/items/add")
def add_item(collection_id: int, data: ItemAddRequest):
    if not (data.task_id or "").strip():
        return R.error("task_id 不能为空", code=400)
    item = collection_dao.add_item(
        collection_id=collection_id,
        task_id=data.task_id.strip(),
        video_id=data.video_id or "",
        platform=data.platform or "",
        sort_order=data.sort_order,
    )
    if item is None:
        return R.error("合集不存在", code=404)
    return R.success(data=item)


@router.delete("/{collection_id}/items/{item_id}")
def remove_item(collection_id: int, item_id: int):
    if not collection_dao.remove_item(collection_id, item_id):
        return R.error("条目不存在", code=404)
    return R.success(data={"deleted": item_id})


@router.post("/items/{item_id}/status")
def update_item_status(item_id: int, data: ItemStatusRequest):
    try:
        item = collection_dao.update_item_status(item_id, data.learning_status)
    except ValueError as exc:
        return R.error(str(exc), code=400)
    if not item:
        return R.error("条目不存在", code=404)
    return R.success(data=item)
