"""笔记产物读取（Markdown 正文是唯一源真值）。

markdown-v2 起笔记就是纯 Markdown（含 `*Content-[mm:ss]` / `*Screenshot-[mm:ss]`
标记协议的后处理结果）；structured-v1 时代的 note_json 不再被读取。
"""
import json
from pathlib import Path
from typing import Optional

from app.utils.path_helper import get_note_results_dir
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _note_dir() -> Path:
    return Path(get_note_results_dir())


def load_note_markdown(task_id: str) -> Optional[str]:
    """读取笔记 Markdown（后处理完成后的最终文本）。"""
    result_file = _note_dir() / f"{task_id}.json"
    if result_file.exists():
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            markdown = data.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                return markdown
        except Exception as exc:
            logger.warning(f"读取 {result_file} 失败：{exc}")
    md_file = _note_dir() / f"{task_id}_markdown.md"
    if md_file.exists():
        try:
            return md_file.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning(f"读取 {md_file} 失败：{exc}")
    return None
