"""BiliNote MCP 服务（Streamable HTTP，挂载在 /mcp）。

把核心四件套暴露给 AI 客户端（Claude / Cursor 等 MCP 客户端配 http://<host>:8483/mcp 即用）：

    generate_note     提交视频 → 结构化笔记任务（异步，返回 task_id）
    list_notes        已完成笔记列表
    get_task_status   任务运行状态（阶段 / 进度 / 失败原因）
    get_note          读取结构化笔记（note_json + Markdown）

工具实现直接复用 /api 路由背后的同一批服务函数，行为与 HTTP API 完全一致。
"""
import os
import threading
import uuid
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from app.services import note_store, task_status
from app.utils.logger import get_logger
from app.utils.path_helper import get_note_results_dir

logger = get_logger(__name__)

mcp = FastMCP(
    "bilinote",
    instructions=(
        "BiliNote 视频笔记助手：提交视频生成结构化笔记、查询任务进度、读取笔记内容。"
        "generate_note 是异步任务，提交后用 get_task_status 轮询，完成后再 get_note 取内容。"
    ),
    # 子应用路由挂在 /mcp；FastAPI 侧以 Mount("") 兜底，/mcp 精确命中不重定向
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)


# ---------------------------------------------------------------- 工具


def _detect_platform(video_url: str) -> Optional[str]:
    u = (video_url or "").lower()
    if "bilibili.com" in u or "b23.tv" in u:
        return "bilibili"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "douyin.com" in u or "v.douyin.com" in u:
        return "douyin"
    if "kuaishou.com" in u:
        return "kuaishou"
    return None


def _resolve_model(model_name: str, provider_id: str) -> tuple[Optional[str], Optional[str], str]:
    """MCP 调用方通常不知道内部 id：缺省时取第一个供应商的第一个模型。"""
    if model_name and provider_id:
        return model_name, provider_id, ""
    from app.db.model_dao import get_models_by_provider
    from app.services.provider import ProviderService

    providers = ProviderService.get_all_providers() or []
    if not providers:
        return None, None, "还没有配置模型供应商：先在 Web「设置 → 模型供应商」里添加"
    provider = providers[0]
    pid = str(provider["id"])
    if not model_name:
        models = get_models_by_provider(provider["id"]) or []
        names = [m["model_name"] for m in models]
        if not names:
            return None, None, f"供应商「{provider['name']}」还没有登记模型"
        model_name = names[0]
    return model_name, pid, ""


@mcp.tool()
def generate_note(
    video_url: str,
    model_name: str = "",
    provider_id: str = "",
    style: str = "detailed",
    extras: str = "",
    quality: str = "medium",
    screenshot: bool = False,
    link: bool = True,
) -> Dict[str, Any]:
    """提交「视频 → 结构化笔记」任务（异步执行，立即返回 task_id）。

    video_url: 视频链接（B站 / YouTube / 抖音 / 快手）。
    model_name / provider_id 可留空，自动用第一个已配置供应商的默认模型。
    style: 笔记风格（detailed 详细 / minimal 精简 / academic 学术 / tutorial 教程 等）。
    extras: 额外要求，会作为补充指令传给模型。
    返回后用 get_task_status 轮询进度，完成后用 get_note 读取笔记。
    """
    from app.enmus.note_enums import DownloadQuality
    from app.enmus.task_status_enums import TaskStatus
    from app.routers.note import run_note_task

    platform = _detect_platform(video_url)
    if not platform:
        return {"error": f"没识别出视频平台（支持 B站 / YouTube / 抖音 / 快手）：{video_url}"}

    model_name, provider_id, err = _resolve_model(model_name, provider_id)
    if err:
        return {"error": err}

    # 与 /api/generate_note 相同的就绪门禁：本地转写模型没下载好就先拒绝
    from app.services.transcriber_config_manager import TranscriberConfigManager

    readiness = TranscriberConfigManager().is_model_ready()
    if not readiness["ready"]:
        return {"error": readiness["reason"], "detail": readiness}

    task_id = str(uuid.uuid4())
    task_status.update_status(task_id, TaskStatus.PENDING, message="任务已进入队列")

    def _run():
        try:
            run_note_task(
                task_id, video_url, platform, DownloadQuality(quality),
                link, screenshot, model_name, provider_id,
                ["toc", "link", "summary"], style, extras,
            )
        except Exception as e:  # 线程里兜底记录，避免异常静默
            logger.exception(f"MCP generate_note 任务失败 (task_id={task_id})")
            task_status.update_status(task_id, TaskStatus.FAILED, message="任务失败", error=str(e))

    threading.Thread(target=_run, daemon=True).start()
    return {
        "task_id": task_id,
        "message": "任务已提交（异步执行），用 get_task_status 轮询进度，完成后用 get_note 读取笔记",
    }


@mcp.tool()
def list_notes(limit: int = 20) -> Dict[str, Any]:
    """列出已完成的笔记（按完成时间倒序），含 task_id / 标题 / 平台 / 时长。"""
    limit = max(1, min(limit, 100))
    items = []
    for doc in task_status.list_statuses(limit=100):
        if doc.get("status") != "SUCCESS":
            continue
        task_id = doc.get("task_id", "")
        meta: Dict[str, Any] = {}
        result_path = os.path.join(get_note_results_dir(), f"{task_id}.json")
        if os.path.exists(result_path):
            import json

            try:
                with open(result_path, "r", encoding="utf-8") as rf:
                    result = json.load(rf)
                meta = result.get("audio_meta") or {}
            except Exception:
                meta = {}
        note = note_store.load_note(task_id) or {}
        items.append({
            "task_id": task_id,
            "title": note.get("title") or meta.get("title") or task_id,
            "platform": meta.get("platform"),
            "duration": meta.get("duration"),
            "updated_at": doc.get("updated_at"),
            "tags": note.get("tags") or [],
        })
        if len(items) >= limit:
            break
    return {"count": len(items), "notes": items}


@mcp.tool()
def get_task_status(task_id: str) -> Dict[str, Any]:
    """查询任务运行状态：阶段 / 步骤 / 进度 / 耗时 / 失败原因；完成后含笔记是否就绪。"""
    doc = task_status.read_status(task_id)
    if not doc:
        return {"error": f"找不到任务 {task_id}"}
    doc = dict(doc)
    doc["note_ready"] = doc.get("status") == "SUCCESS" and note_store.load_note(task_id) is not None
    return doc


@mcp.tool()
def get_note(task_id: str) -> Dict[str, Any]:
    """读取一篇结构化笔记：note_json（章节/小节/公式/表格）+ 派生 Markdown。"""
    note = note_store.load_note(task_id)
    markdown = note_store.load_note_markdown(task_id)
    if not note and not markdown:
        return {"error": f"找不到笔记 {task_id}（任务可能未完成）"}
    return {"task_id": task_id, "note": note, "markdown": markdown}
