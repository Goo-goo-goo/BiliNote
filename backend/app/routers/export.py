"""导出接口（P3）：单篇笔记 / 复习资料 → Markdown 或 HTML。"""
from fastapi import APIRouter, Response

from app.services.note_store import load_note_markdown
from app.utils.note_export import markdown_to_html
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
    markdown = load_note_markdown(task_id)
    if not markdown:
        return R.error("笔记不存在或无可导出内容", code=404)

    title = "视频笔记"
    for line in markdown.splitlines():
        if line.startswith("# "):
            title = line[2:].strip() or title
            break

    if format == "md":
        return _file_response(markdown, f"{task_id}.md", "text/markdown")

    if format == "html":
        html_text = markdown_to_html(markdown, title=title)
        return _file_response(html_text, f"{task_id}.html", "text/html")

    return R.error("format 只支持 md / html", code=400)
