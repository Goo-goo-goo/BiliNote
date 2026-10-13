from dataclasses import dataclass

from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult


@dataclass
class NoteResult:
    markdown: str                  # GPT 直出的 Markdown 笔记正文（markdown-v2 源真值）
    transcript: TranscriptResult   # Whisper 转写结果
    audio_meta: AudioDownloadResult  # 音频下载的元信息（title、duration、封面等）
