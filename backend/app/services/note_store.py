"""笔记产物读取（{task_id}.json 的 note 字段 / {task_id}.note.json）。

structured-v1 起 note_json 是源真值，派生 Markdown 与它一起落盘；
旧笔记只有 Markdown，此时返回 None，由调用方决定兜底策略。
"""
import json
from pathlib import Path
from typing import Optional

from app.utils.path_helper import get_note_results_dir
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _note_dir() -> Path:
    return Path(get_note_results_dir())


def load_note(task_id: str) -> Optional[dict]:
    """读取结构化笔记 note_json；旧笔记返回 None。"""
    note_file = _note_dir() / f"{task_id}.note.json"
    if note_file.exists():
        try:
            data = json.loads(note_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("chapters"):
                return data
        except Exception as exc:
            logger.warning(f"读取 {note_file} 失败：{exc}")

    result_file = _note_dir() / f"{task_id}.json"
    if result_file.exists():
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            note = data.get("note")
            if isinstance(note, dict) and note.get("chapters"):
                return note
        except Exception as exc:
            logger.warning(f"读取 {result_file} 失败：{exc}")
    return None


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
