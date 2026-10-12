"""复习资料接口（P3）。

生成是长任务：建记录后丢进线程池后台跑，进度写 progress 字段供轮询；
产物 content 存 JSON，导出走 /export 接口（Markdown / HTML）。
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import collection_dao, review_dao
from app.services.note_store import load_note
from app.services.review_material import generate_review_material
from app.services.gpt_resolver import resolve_gpt
from app.services.task_serial_executor import task_serial_executor
from app.utils.logger import get_logger
from app.utils.response import ResponseWrapper as R

logger = get_logger(__name__)
router = APIRouter(prefix="/review", tags=["review"])


class ReviewGenerateRequest(BaseModel):
    collection_id: int
    model_name: Optional[str] = None
    provider_id: Optional[str] = None
    detail_mode: Optional[str] = "full"   # full / brief
    title: Optional[str] = ""


def _run_generation(material_id: int, collection_id: int, title: str,
                    model_name: Optional[str], provider_id: Optional[str],
                    detail_mode: str) -> None:
    try:
        items = collection_dao.list_items(collection_id)
        if not items:
            raise ValueError("合集里还没有笔记条目")
        notes, task_ids = [], []
        for item in items:
            note = load_note(item["task_id"])
            if note:
                notes.append(note)
                task_ids.append(item["task_id"])
            else:
                logger.info(f"跳过无结构化笔记的条目: {item['task_id']}")

        gpt = resolve_gpt(model_name, provider_id)
        content = generate_review_material(
            material_id=material_id,
            title=title,
            notes=notes,
            task_ids=task_ids,
            gpt=gpt,
            detail_mode=detail_mode,
            progress_cb=lambda msg: review_dao.update_progress(material_id, msg),
        )
        review_dao.finalize_material(material_id, content.get("title") or title, content)
    except Exception as exc:
        logger.error(f"复习资料生成失败 (material_id={material_id})：{exc}", exc_info=True)
        review_dao.fail_material(material_id, str(exc))


@router.post("/generate")
def generate(data: ReviewGenerateRequest):
    collection = collection_dao.get_collection(data.collection_id)
    if not collection:
        return R.error("合集不存在", code=404)
    detail_mode = data.detail_mode if data.detail_mode in ("full", "brief") else "full"
    title = (data.title or "").strip() or f"{collection['name']}·复习资料"
    material = review_dao.create_material(data.collection_id, title=title, detail_mode=detail_mode)
    task_serial_executor.run(
        _run_generation,
        material["id"], data.collection_id, title,
        data.model_name, data.provider_id, detail_mode,
    )
    return R.success(data=material)


@router.get("/list")
def list_materials(collection_id: Optional[int] = None):
    return R.success(data=review_dao.list_materials(collection_id))


@router.get("/{material_id}")
def get_material(material_id: int):
    material = review_dao.get_material(material_id)
    if not material:
        return R.error("复习资料不存在", code=404)
    return R.success(data=material)


@router.delete("/{material_id}")
def delete_material(material_id: int):
    if not review_dao.delete_material(material_id):
        return R.error("复习资料不存在", code=404)
    return R.success(data={"deleted": material_id})
