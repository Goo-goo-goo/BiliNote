# app/routers/note.py
import json
import os
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, validator, field_validator, model_validator
from dataclasses import asdict

from app.db.video_task_dao import get_task_by_video
from app.enmus.exception import NoteErrorEnum
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.services.note import NoteGenerator, logger
from app.services import task_status
from app.services.task_serial_executor import task_serial_executor
from app.utils.path_helper import get_note_results_dir, get_upload_dir
from app.utils.response import ResponseWrapper as R
from app.utils.url_parser import extract_video_id, normalize_video_url
from app.validators.video_url_validator import is_supported_video_url
from app.enmus.task_status_enums import TaskStatus

# from app.services.downloader import download_raw_audio
# from app.services.whisperer import transcribe_audio

router = APIRouter()


class RecordRequest(BaseModel):
    video_id: str
    platform: str


class VideoRequest(BaseModel):
    video_url: str
    platform: str
    quality: DownloadQuality
    screenshot: Optional[bool] = False
    link: Optional[bool] = False
    model_name: str
    provider_id: str
    task_id: Optional[str] = None
    format: Optional[list] = []
    style: str = None
    extras: Optional[str]=None
    video_understanding: Optional[bool] = False
    video_interval: Optional[int] = 0
    grid_size: Optional[list] = []
    # 客户端（如浏览器插件）已经在用户浏览器里抓到字幕，直接传给后端复用，
    # 跳过 download_subtitles 和音频转写。形如：
    #   {"language": "zh", "full_text": "...", "segments": [{"start","end","text"}, ...]}
    prefetched_transcript: Optional[dict] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_url(cls, data):
        # 稍后再看/收藏夹/带追踪参数的 B 站链接先规范化成标准 /video/BVxxx 形式，
        # 后续校验和 yt-dlp 下载拿到的都是干净链接
        if isinstance(data, dict) and data.get("platform") == "bilibili" and data.get("video_url"):
            data["video_url"] = normalize_video_url(str(data["video_url"]))
        return data

    @field_validator("video_url")
    def validate_supported_url(cls, v):
        url = str(v)
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            # 是网络链接，继续用原有平台校验
            if not is_supported_video_url(url):
                raise NoteError(code=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code,
                                message=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message)

        return v


NOTE_OUTPUT_DIR = get_note_results_dir()
UPLOAD_DIR = get_upload_dir()


def save_note_to_file(task_id: str, note):
    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(note), f, ensure_ascii=False, indent=2)


def _persist_prefetched_transcript(task_id: str, transcript: dict) -> None:
    """把客户端预取的字幕写到 NoteGenerator 期望的转写缓存文件里。

    NoteGenerator.generate 会优先读 <task_id>_transcript.json，命中即跳过 download_subtitles
    与音频转写流程。要求字段：language(可空)/full_text/segments[{start,end,text}]
    """
    segments = transcript.get("segments") or []
    cleaned_segments = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        cleaned_segments.append({
            "start": float(s.get("start", 0)),
            "end": float(s.get("end", 0)),
            "text": text,
        })
    if not cleaned_segments:
        raise ValueError("prefetched_transcript 没有可用的 segments")

    full_text = transcript.get("full_text") or " ".join(s["text"] for s in cleaned_segments)
    payload = {
        "language": transcript.get("language") or "zh",
        "full_text": full_text,
        "segments": cleaned_segments,
    }

    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    target = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}_transcript.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"已写入客户端预取字幕缓存: {target} ({len(cleaned_segments)} 段)")


def run_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                  link: bool = False, screenshot: bool = False, model_name: str = None, provider_id: str = None,
                  _format: list = None, style: str = None, extras: str = None, video_understanding: bool = False,
                  video_interval=0, grid_size=[]
                  ):

    if not model_name or not provider_id:
        raise HTTPException(status_code=400, detail="请选择模型和提供者")

    def _execute_note_task():
        return NoteGenerator().generate(
            video_url=video_url,
            platform=platform,
            quality=quality,
            task_id=task_id,
            model_name=model_name,
            provider_id=provider_id,
            link=link,
            _format=_format,
            style=style,
            extras=extras,
            screenshot=screenshot,
            video_understanding=video_understanding,
            video_interval=video_interval,
            grid_size=grid_size,
        )

    logger.info(f"任务进入执行队列 (task_id={task_id})")
    note = task_serial_executor.run(_execute_note_task)
    logger.info(f"Note generated: {task_id}")
    if not note or not note.markdown:
        logger.warning(f"任务 {task_id} 执行失败，跳过保存")
        return
    save_note_to_file(task_id, note)

    # 自动建立向量索引（用于 AI 问答），失败不影响笔记生成
    try:
        from app.services.vector_store import VectorStoreManager
        VectorStoreManager().index_task(task_id)
    except Exception as e:
        logger.warning(f"向量索引失败（不影响笔记）: {e}")


@router.post('/delete_task')
def delete_task(data: RecordRequest):
    try:
        # TODO: 待持久化完成
        # NoteGenerator().delete_note(video_id=data.video_id, platform=data.platform)
        return R.success(msg='删除成功')
    except Exception as e:
        return R.error(msg=e)


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_location = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_location, "wb+") as f:
        f.write(await file.read())

    # 假设你静态目录挂载了 /uploads
    return R.success({"url": f"/uploads/{file.filename}"})


@router.post("/generate_note")
def generate_note(data: VideoRequest, background_tasks: BackgroundTasks):
    try:
        # 就绪门禁：本地转写引擎（fast-whisper / mlx-whisper）必须等模型下载完才能跑视频，
        # 否则任务会卡在首次下载（慢 / OOM / 截断），用户只看到一个静默失败的任务。
        # 客户端已抓好字幕（prefetched_transcript）则不需要转写，跳过检查。
        if not data.prefetched_transcript:
            from app.services.transcriber_config_manager import TranscriberConfigManager
            readiness = TranscriberConfigManager().is_model_ready()
            if not readiness["ready"]:
                logger.warning(f"拒绝 generate_note：{readiness['reason']}")
                return R.error(
                    msg=readiness["reason"],
                    code=300102,
                    data={
                        "reason": "transcriber_model_not_ready",
                        "transcriber_type": readiness["transcriber_type"],
                        "model_size": readiness["model_size"],
                        "downloading": readiness["downloading"],
                    },
                )

        video_id = extract_video_id(data.video_url, data.platform)
        # if not video_id:
        #     raise HTTPException(status_code=400, detail="无法提取视频 ID")
        # existing = get_task_by_video(video_id, data.platform)
        # if existing:
        #     return R.error(
        #         msg='笔记已生成，请勿重复发起',
        #
        #     )
        if data.task_id:
            # 如果传了task_id，说明是重试！
            task_id = data.task_id
            logger.info(f"重试模式，复用已有 task_id={task_id}")
        else:
            # 正常新建任务
            task_id = str(uuid.uuid4())

        # 统一先写入 PENDING，表示已进入队列等待串行执行
        NoteGenerator()._update_status(task_id, TaskStatus.PENDING)

        # 客户端已经抓好字幕的话，写到转写缓存文件，NoteGenerator 的 cache-hit 逻辑会直接用上
        if data.prefetched_transcript:
            try:
                _persist_prefetched_transcript(task_id, data.prefetched_transcript)
            except Exception as e:
                logger.warning(f"写入预取字幕失败 (task_id={task_id}): {e}")

        background_tasks.add_task(run_note_task, task_id, data.video_url, data.platform, data.quality, data.link,
                                  data.screenshot, data.model_name, data.provider_id, data.format, data.style,
                                  data.extras, data.video_understanding, data.video_interval, data.grid_size)
        return R.success({"task_id": task_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
def list_tasks(limit: int = 50):
    """全局任务面板：所有任务的运行状态（谁在跑、第几步、在干什么、卡了多久）。"""
    return R.success(data=task_status.list_statuses(limit=max(1, min(limit, 200))))


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    """任务运行状态（富文档）：阶段/步骤/子步骤/进度/耗时/阶段轨迹/失败原因。"""
    status_doc = task_status.read_status(task_id)
    result_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json")

    # 有状态文件：返回富状态文档（含 history / progress / stale_seconds 等）
    if status_doc:
        status = status_doc.get("status")

        if status == TaskStatus.SUCCESS.value:
            payload = dict(status_doc)
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as rf:
                    payload["result"] = json.load(rf)
            else:
                # 理论上不会出现，保险处理：沿用旧契约报回排队态
                payload["status"] = TaskStatus.PENDING.value
                payload["message"] = "任务完成，但结果文件未找到"
            return R.success(payload)

        if status == TaskStatus.FAILED.value:
            # 保持旧的错误包结构，同时把富状态文档放进 data（history / error 可查）
            return R.error(status_doc.get("error") or status_doc.get("message") or "任务失败",
                           code=500, data=status_doc)

        return R.success(status_doc)

    # 没有状态文件，但有结果：老任务（状态文件被清理过）
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            result_content = json.load(f)
        return R.success({
            "task_id": task_id,
            "status": TaskStatus.SUCCESS.value,
            "label": TaskStatus.description(TaskStatus.SUCCESS),
            "message": "完成",
            "result": result_content,
            "finished": True,
        })

    # 什么都没有：排队占位
    return R.success({
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "label": TaskStatus.description(TaskStatus.PENDING),
        "message": "任务排队中（未发现状态文件）",
        "step": 0,
        "total_steps": 6,
        "progress": 0.0,
        "finished": False,
        "history": [],
    })
