from abc import ABC
import os

from openai import BadRequestError

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.transcriber_config_manager import TranscriberConfigManager
from app.transcriber.base import Transcriber
from app.utils.openai_client import build_openai_client


class OpenAIApiTranscriber(Transcriber, ABC):
    """自定义 OpenAI 兼容 ASR 服务（如 whisper.cpp server、FunASR、vLLM 等）。

    走 OpenAI SDK 的 audio.transcriptions 接口：POST {base_url}/audio/transcriptions，
    multipart 上传音频文件。base_url / api_key / model 从转写器配置读取
    （可通过转写器配置接口修改，持久化在 config/transcriber.json）。
    """

    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        cfg = TranscriberConfigManager().get_config()
        self.base_url = (base_url if base_url is not None else cfg.get("openai_api_base_url") or "").strip()
        self.api_key = (api_key if api_key is not None else cfg.get("openai_api_key") or "").strip()
        self.model = (model if model is not None else cfg.get("openai_api_model") or "whisper-1").strip()
        if not self.base_url:
            raise ValueError(
                "自定义 ASR 服务地址未配置，请先在「设置 → 音频转写配置」填写接口地址（如 http://127.0.0.1:9000/v1）"
            )

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        # 本地/自托管服务通常不校验 key，但 build_openai_client 要求非空（空 key
        # 会让 httpx 拼出非法 header `Bearer `），未填时给个占位串
        client = build_openai_client(
            api_key=self.api_key or "sk-none",
            base_url=self.base_url,
            key_label="自定义 ASR 服务的 API Key",
        )
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            try:
                # verbose_json 带时间轴分段；部分兼容服务不支持该参数
                transcription = client.audio.transcriptions.create(
                    file=(filename, f.read()),
                    model=self.model,
                    response_format="verbose_json",
                )
            except BadRequestError:
                # 服务不支持 verbose_json 时退回默认 json（只有纯文本，无分段）
                f.seek(0)
                transcription = client.audio.transcriptions.create(
                    file=(filename, f.read()),
                    model=self.model,
                )
                text = (transcription.text or "").strip()
                return TranscriptResult(
                    language=None,
                    full_text=text,
                    segments=[TranscriptSegment(start=0.0, end=0.0, text=text)] if text else [],
                    raw=transcription.to_dict() if hasattr(transcription, "to_dict") else None,
                )

        segments = []
        full_text = ""
        for seg in transcription.segments or []:
            text = seg.text.strip()
            full_text += text + " "
            segments.append(TranscriptSegment(
                start=seg.start,
                end=seg.end,
                text=text,
            ))
        if not full_text.strip():
            full_text = (transcription.text or "").strip()

        return TranscriptResult(
            language=transcription.language,
            full_text=full_text.strip(),
            segments=segments,
            raw=transcription.to_dict(),
        )
