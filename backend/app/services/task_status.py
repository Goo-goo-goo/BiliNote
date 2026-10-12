"""任务运行状态（统一写入/读取/列表）。

解决「任务跑到哪一步、在干什么、是不是卡住了」不可见的问题。状态持久化在
`{task_id}.status.json`（与旧格式同文件，`status`/`message` 字段保留，旧客户端兼容），
每次更新写入富信息文档：

    {
      "task_id", "status", "label", "step", "total_steps",
      "message",          # 阶段级说明（人读）
      "detail",           # 子步骤，如「分段总结 2/3」「正在下载字幕」
      "progress",         # 0~1 粗粒度进度（阶段锚点 + 子步骤插值）
      "created_at", "updated_at", "elapsed_seconds", "stale_seconds",
      "history": [...],   # 阶段轨迹（每个阶段一条，含耗时）
      "error"
    }

写入是原子替换（tmp + rename），读取对坏文件容错。
"""
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.enmus.task_status_enums import TaskStatus
from app.utils.logger import get_logger
from app.utils.path_helper import get_note_results_dir

logger = get_logger(__name__)

HISTORY_LIMIT = 50

# 阶段顺序与整体进度锚点（0~1），子步骤进度在锚点区间内插值
PHASES: List[Dict] = [
    {"status": TaskStatus.PENDING, "step": 0, "progress": 0.0},
    {"status": TaskStatus.PARSING, "step": 1, "progress": 0.05},
    {"status": TaskStatus.DOWNLOADING, "step": 2, "progress": 0.25},
    {"status": TaskStatus.TRANSCRIBING, "step": 3, "progress": 0.5},
    {"status": TaskStatus.SUMMARIZING, "step": 4, "progress": 0.85},
    {"status": TaskStatus.FORMATTING, "step": 5, "progress": 0.92},
    {"status": TaskStatus.SAVING, "step": 6, "progress": 0.97},
    {"status": TaskStatus.SUCCESS, "step": 6, "progress": 1.0},
]
WORK_STEPS = 6  # 步骤条总步数（不含 PENDING / 终态）

_STATUS_LOCK = threading.Lock()

_STATUS_BY_VALUE = {p["status"].value: p for p in PHASES}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_path(task_id: str) -> Path:
    return Path(get_note_results_dir()) / f"{task_id}.status.json"


def _label(status: str) -> str:
    try:
        return TaskStatus.description(TaskStatus(status))
    except Exception:
        return status


def _phase_meta(status: str) -> Dict:
    return _STATUS_BY_VALUE.get(status, {"status": status, "step": 0, "progress": 0.0})


def _read_doc(task_id: str) -> Dict:
    path = _status_path(task_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning(f"读取状态文件失败 {path}: {exc}")
        return {}


def _write_doc(task_id: str, doc: Dict) -> None:
    path = _status_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _base_doc(task_id: str) -> Dict:
    now = _now_iso()
    return {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "label": _label(TaskStatus.PENDING.value),
        "step": 0,
        "total_steps": WORK_STEPS,
        "message": "任务已提交",
        "detail": "",
        "progress": 0.0,
        "created_at": now,
        "updated_at": now,
        "history": [],
        "error": None,
    }


# ---------------------------------------------------------------- 写入

def update_status(task_id: Optional[str], status, message: Optional[str] = None,
                  detail: Optional[str] = None, progress: Optional[float] = None,
                  error: Optional[str] = None) -> None:
    """更新任务状态（阶段变化会记入 history）。"""
    if not task_id:
        return
    status_value = status.value if isinstance(status, TaskStatus) else str(status)
    with _STATUS_LOCK:
        doc = _read_doc(task_id) or _base_doc(task_id)
        now = _now_iso()
        try:
            created_at = datetime.fromisoformat(doc.get("created_at") or now)
        except ValueError:
            created_at = datetime.fromisoformat(now)

        meta = _phase_meta(status_value)
        is_terminal = status_value in (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value)
        previous = doc.get("status")

        doc["status"] = status_value
        doc["label"] = _label(status_value)
        doc["step"] = meta["step"]
        doc["total_steps"] = WORK_STEPS
        if message is not None:
            doc["message"] = message
        elif is_terminal:
            doc["message"] = "完成" if status_value == TaskStatus.SUCCESS.value else (error or "失败")
        if detail is not None:
            doc["detail"] = detail
        if error is not None or status_value == TaskStatus.FAILED.value:
            doc["error"] = error if error is not None else doc.get("error")
        doc["progress"] = float(progress) if progress is not None else float(meta["progress"])
        doc["updated_at"] = now
        doc["elapsed_seconds"] = round((datetime.fromisoformat(now) - created_at).total_seconds(), 1)

        # 阶段轨迹：状态变化、或同状态但换了说明时追加
        history = doc.setdefault("history", [])
        if (not history) or history[-1].get("status") != status_value or \
                (message is not None and history[-1].get("message") != message):
            history.append({
                "status": status_value,
                "label": _label(status_value),
                "message": doc.get("message", ""),
                "at": now,
                "elapsed": doc["elapsed_seconds"],
            })
            doc["history"] = history[-HISTORY_LIMIT:]

        _write_doc(task_id, doc)


def set_detail(task_id: Optional[str], detail: str, progress: Optional[float] = None) -> None:
    """只更新子步骤（高频调用：如「分段总结 2/3」），不追加 history。"""
    if not task_id:
        return
    with _STATUS_LOCK:
        doc = _read_doc(task_id)
        if not doc:
            return
        now = _now_iso()
        doc["detail"] = detail
        if progress is not None:
            doc["progress"] = float(progress)
        doc["updated_at"] = now
        try:
            created_at = datetime.fromisoformat(doc.get("created_at") or now)
            doc["elapsed_seconds"] = round((datetime.fromisoformat(now) - created_at).total_seconds(), 1)
        except ValueError:
            pass
        _write_doc(task_id, doc)


# ---------------------------------------------------------------- 读取

def read_status(task_id: str) -> Optional[Dict]:
    """读取富状态文档（补算 elapsed / stale，供接口直接返回）。"""
    doc = _read_doc(task_id)
    if not doc:
        return None
    now = datetime.now(timezone.utc)
    try:
        updated = datetime.fromisoformat(doc.get("updated_at") or _now_iso())
    except ValueError:
        updated = now
    try:
        created = datetime.fromisoformat(doc.get("created_at") or _now_iso())
    except ValueError:
        created = now

    doc.setdefault("task_id", task_id)
    doc.setdefault("label", _label(doc.get("status", "")))
    doc.setdefault("total_steps", WORK_STEPS)
    doc.setdefault("history", [])
    doc.setdefault("detail", "")
    if doc.get("progress") is None:
        doc["progress"] = float(_phase_meta(doc.get("status", "")).get("progress", 0.0))
    doc["elapsed_seconds"] = round((now - created).total_seconds(), 1)
    doc["stale_seconds"] = round((now - updated).total_seconds(), 1)
    doc["finished"] = doc.get("status") in (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value)
    return doc


def list_statuses(limit: int = 50) -> List[Dict]:
    """所有任务的运行状态（按最近更新倒序），用于「全局任务面板」。"""
    note_dir = Path(get_note_results_dir())
    if not note_dir.is_dir():
        return []
    result: List[Dict] = []
    for path in note_dir.glob("*.status.json"):
        task_id = path.name[: -len(".status.json")]
        doc = read_status(task_id)
        if not doc:
            continue
        result.append({
            "task_id": task_id,
            "status": doc.get("status"),
            "label": doc.get("label"),
            "step": doc.get("step"),
            "total_steps": doc.get("total_steps"),
            "message": doc.get("message", ""),
            "detail": doc.get("detail", ""),
            "progress": doc.get("progress", 0.0),
            "elapsed_seconds": doc.get("elapsed_seconds"),
            "stale_seconds": doc.get("stale_seconds"),
            "updated_at": doc.get("updated_at"),
            "finished": doc.get("finished"),
            "error": doc.get("error"),
        })
    result.sort(key=lambda d: str(d.get("updated_at") or ""), reverse=True)
    return result[:limit]
