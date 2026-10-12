"""导出接口（P3）：单篇笔记 / 复习资料 → Markdown 或 HTML。"""
from fastapi import APIRouter, Response

from app.db import review_dao
from app.gpt.note_render import note_to_markdown
from app.services.note_store import load_note, load_note_markdown
from app.utils.note_export import note_to_html, review_to_html, review_to_markdown
from app.utils.response import ResponseWrapper as R

router = APIRouter(prefix="/export", tags=["export"])


def _file_response(content: str, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/note/{task_id}")
def export_note(task_id: str, format: str = "md"):
    note = load_note(task_id)
    markdown = load_note_markdown(task_id)

    if format == "md":
        text = markdown or (note_to_markdown(note) if note else None)
        if not text:
            return R.error("笔记不存在或无可导出内容", code=404)
        return _file_response(text, f"{task_id}.md", "text/markdown")

    if format == "html":
        if not note and not markdown:
            return R.error("笔记不存在或无可导出内容", code=404)
        html_text = note_to_html(note or {}, markdown_hint=markdown or "")
        return _file_response(html_text, f"{task_id}.html", "text/html")

    return R.error("format 只支持 md / html", code=400)


@router.get("/review/{material_id}")
def export_review(material_id: int, format: str = "md"):
    material = review_dao.get_material(material_id)
    if not material:
        return R.error("复习资料不存在", code=404)
    if material.get("status") != "done" or not material.get("content"):
        return R.error(f"复习资料尚未生成完成（当前状态：{material.get('status')}）", code=400)

    content = material["content"]
    title = material.get("title") or f"review-{material_id}"
    if format == "md":
        return _file_response(review_to_markdown(content), f"{title}.md", "text/markdown")
    if format == "html":
        return _file_response(review_to_html(content), f"{title}.html", "text/html")
    return R.error("format 只支持 md / html", code=400)
