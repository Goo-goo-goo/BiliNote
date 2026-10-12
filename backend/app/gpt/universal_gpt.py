from app.gpt.base import GPT
from app.gpt.prompt_builder import generate_base_prompt
from app.models.gpt_model import GPTSource
import os
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.gpt.prompt import BASE_PROMPT, AI_SUM, SCREENSHOT, LINK, MERGE_PROMPT, FINALIZE_PROMPT
from app.gpt.utils import fix_markdown
from app.gpt.request_chunker import RequestChunker
from app.models.transcriber_model import TranscriptSegment
from app.utils.path_helper import get_note_results_dir
from datetime import timedelta
from typing import List


class UniversalGPT(GPT):
    def __init__(self, client, model: str, temperature: float = 0.7):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.screenshot = False
        self.link = False
        self.max_request_bytes = int(os.getenv("OPENAI_MAX_REQUEST_BYTES", str(45 * 1024 * 1024)))
        self.checkpoint_dir = Path(get_note_results_dir())
        # 初始化时缓存重试配置，避免每次请求重复读取环境变量
        self._max_retry_attempts = max(1, int(os.getenv("OPENAI_RETRY_ATTEMPTS", "3")))
        self._retry_base_backoff = float(os.getenv("OPENAI_RETRY_BACKOFF_SECONDS", "1.5"))

    def _format_time(self, seconds: float) -> str:
        """转写时间戳 → 规范 HH:MM:SS（旧实现对超 1 小时会把小时位截掉）。"""
        total = int(seconds)
        hh, rem = divmod(total, 3600)
        mm, ss = divmod(rem, 60)
        return f"{hh:02d}:{mm:02d}:{ss:02d}"

    def _build_segment_text(self, segments: List[TranscriptSegment]) -> str:
        return "\n".join(
            f"{self._format_time(seg.start)} - {seg.text.strip()}"
            for seg in segments
        )

    def ensure_segments_type(self, segments) -> List[TranscriptSegment]:
        return [TranscriptSegment(**seg) if isinstance(seg, dict) else seg for seg in segments]

    def create_messages(self, segments: List[TranscriptSegment], **kwargs):

        content_text = generate_base_prompt(
            title=kwargs.get('title'),
            segment_text=self._build_segment_text(segments),
            tags=kwargs.get('tags'),
            _format=kwargs.get('_format'),
            style=kwargs.get('style'),
            extras=kwargs.get('extras'),
        )

        video_img_urls = kwargs.get('video_img_urls', [])

        content: list[dict] | str
        if video_img_urls:
            # 有截图时走 OpenAI 多模态 content 数组（text + image_url）
            content = [{"type": "text", "text": content_text}]
            for url in video_img_urls:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": url,
                        "detail": "auto"
                    }
                })
        else:
            # 纯文本场景退回 string content：DeepSeek deepseek-chat 等非多模态模型
            # 不识别 [{"type":"text",...}] 数组形态，会返回 invalid_request_error
            # （issue #282）。OpenAI 规范本身也允许 content 为 string。
            content = content_text

        messages = [{
            "role": "user",
            "content": content
        }]

        return messages

    def list_models(self):
        return self.client.models.list()

    def _estimate_messages_bytes(self, messages: list) -> int:
        import json
        return len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))

    def _build_merge_messages(self, partials: list) -> list:
        merge_text = MERGE_PROMPT + "\n\n" + "\n\n---\n\n".join(partials)
        # 合并阶段没有图片，直接用 string content 兼容非多模态模型（issue #282）
        return [{
            "role": "user",
            "content": merge_text
        }]

    def _checkpoint_path(self, checkpoint_key: str) -> Path:
        safe_key = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in checkpoint_key)
        return self.checkpoint_dir / f"{safe_key}.gpt.checkpoint.json"

    def _build_source_signature(self, source: GPTSource) -> str:
        payload = {
            # 提示词管线版本：structured-v1 切换后让旧 Markdown 管线的 checkpoint 自动失效
            "pipeline": "structured-v1",
            "model": self.model,
            "temperature": self.temperature,
            "max_request_bytes": self.max_request_bytes,
            "title": source.title,
            "tags": source.tags,
            "format": source._format,
            "style": source.style,
            "extras": source.extras,
            "video_img_urls": source.video_img_urls or [],
            "segments": [
                {
                    "start": getattr(seg, "start", None),
                    "end": getattr(seg, "end", None),
                    "text": getattr(seg, "text", "")
                }
                for seg in source.segment
            ],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_checkpoint(self, checkpoint_key: str, source_signature: str) -> dict | None:
        path = self._checkpoint_path(checkpoint_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("source_signature") != source_signature:
                path.unlink(missing_ok=True)
                return None
            return data
        except Exception:
            path.unlink(missing_ok=True)
            return None

    def _save_checkpoint(self, checkpoint_key: str, source_signature: str, partials: list, phase: str) -> None:
        path = self._checkpoint_path(checkpoint_key)
        data = {
            "version": 1,
            "source_signature": source_signature,
            "phase": phase,
            "partials": partials,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def _clear_checkpoint(self, checkpoint_key: str) -> None:
        self._checkpoint_path(checkpoint_key).unlink(missing_ok=True)

    @staticmethod
    def _is_insufficient_quota_error(exc: Exception) -> bool:
        raw = str(exc)
        return (
            "insufficient_user_quota" in raw
            or "预扣费额度失败" in raw
            or "insufficient quota" in raw.lower()
        )

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        raw = str(exc).lower()
        retryable_tokens = (
            "error code: 524",
            "bad_response_status_code",
            "timed out",
            "timeout",
            "rate limit",
            "error code: 429",
            "error code: 500",
            "error code: 502",
            "error code: 503",
            "error code: 504",
            "apiconnectionerror",
            "connection error",
            "service unavailable",
        )
        if any(token in raw for token in retryable_tokens):
            return True

        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        return status in {408, 409, 429, 500, 502, 503, 504, 524}

    @staticmethod
    def _is_temperature_unsupported_error(exc: Exception) -> bool:
        """OpenAI o1/o3/gpt-5 系列等新模型不接受自定义 temperature，
        只允许默认值 1，传 0.7 会报 `'temperature' does not support 0.7 ...`。"""
        raw = str(exc).lower()
        return "temperature" in raw and (
            "does not support" in raw
            or "unsupported_value" in raw
            or "only the default" in raw
        )

    def _do_create(self, messages: list):
        """单次调用。如果模型拒绝自定义 temperature，就地去掉该参数再试一次
        （不消耗外层的重试次数预算），仍失败则把异常抛给外层重试逻辑。"""
        try:
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
        except Exception as exc:
            if self._is_temperature_unsupported_error(exc):
                print(f"[universal_gpt] 模型 {self.model} 不支持自定义 temperature，改用默认值重试")
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                )
            raise

    def _chat_completion_create(self, messages: list):
        last_exc = None
        for attempt in range(self._max_retry_attempts):
            try:
                return self._do_create(messages)
            except Exception as exc:
                last_exc = exc
                if attempt == self._max_retry_attempts - 1 or not self._is_retryable_error(exc):
                    raise
                sleep_seconds = self._retry_base_backoff * (2 ** attempt)
                time.sleep(sleep_seconds)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("chat completion failed without exception")

    def _merge_partials(self, partials: list, checkpoint_key: str | None, source_signature: str | None) -> str:
        def build_messages(texts, *_args, **_kwargs):
            return self._build_merge_messages(texts)

        merge_chunker = RequestChunker(
            lambda *_args, **_kwargs: [],
            self.max_request_bytes,
            self._estimate_messages_bytes
        )

        current_partials = list(partials)
        while len(current_partials) > 1:
            groups = merge_chunker.group_texts_by_budget(current_partials, build_messages)
            new_partials = []
            for group_idx, group in enumerate(groups):
                messages = build_messages(group)
                try:
                    response = self._chat_completion_create(messages)
                except Exception as exc:
                    if checkpoint_key and source_signature:
                        self._save_checkpoint(checkpoint_key, source_signature, current_partials, "merge")
                    raise

                new_partials.append(response.choices[0].message.content.strip())

                if checkpoint_key and source_signature:
                    remaining_partials = []
                    for remaining_group in groups[group_idx + 1:]:
                        remaining_partials.extend(remaining_group)
                    resumable_partials = new_partials + remaining_partials
                    self._save_checkpoint(checkpoint_key, source_signature, resumable_partials, "merge")

            current_partials = new_partials

        return current_partials[0]

    # ---------------------------------------------------------- structured-v1

    def _chat_json(self, messages: list, purpose: str = "笔记"):
        """调用模型并稳健解析 JSON；解析失败把错误回喂重试（共 3 次机会）。

        HTTP / 网络层错误不在这里重试（由 _chat_completion_create 的重试预算负责），
        也不会被误包装成「JSON 解析失败」。
        """
        from app.gpt.note_render import extract_json

        history = list(messages)
        last_err = ""
        for attempt in range(3):
            response = self._chat_completion_create(history)
            text = (response.choices[0].message.content or "").strip()
            try:
                return extract_json(text)
            except ValueError as exc:
                last_err = str(exc)
                print(f"[universal_gpt] {purpose} JSON 解析失败（第 {attempt + 1} 次）：{last_err}")
                if attempt < 2:
                    history = history + [{
                        "role": "user",
                        "content": (
                            "你上一次的输出不是合法 JSON。请严格只输出一个 JSON 对象，"
                            "不要包含任何解释、注释或 Markdown 代码块。错误信息：" + last_err
                        ),
                    }]
        raise ValueError(f"{purpose} JSON 解析失败：{last_err}")

    def chat_json(self, messages: list, purpose: str = "内容"):
        """通用 JSON 对话入口（自测题、复习资料等非笔记场景复用同一套健壮解析）。"""
        return self._chat_json(messages, purpose=purpose)

    def _normalize_sections_text(self, raw) -> str:
        """map / merge 产物 → 规范 `{"sections": [...]}` JSON 文本。

        checkpoint 只存字符串列表，故统一序列化为文本。
        """
        from app.gpt.note_render import extract_sections, normalize_section

        sections = []
        for item in extract_sections(raw):
            section = normalize_section(item)
            if section:
                sections.append(section)
        return json.dumps({"sections": sections}, ensure_ascii=False)

    def _finalize_messages(self, sections_text: str, source: GPTSource) -> list:
        header = (
            f"视频标题：{source.title}\n"
            f"视频标签：{source.tags if source.tags else '无'}\n\n"
        )
        # finalize 阶段没有图片，用 string content 兼容非多模态模型（issue #282）
        return [{"role": "user", "content": FINALIZE_PROMPT + header + sections_text}]

    def _finalize_note(self, sections_text: str, source: GPTSource,
                       checkpoint_key: str | None = None,
                       source_signature: str | None = None) -> dict:
        """最后一步：合并后的小节 → 整篇笔记 JSON（归一化后返回）。"""
        from app.gpt.note_render import normalize_note

        if checkpoint_key and source_signature:
            # 合并已完成：断点只留合并结果，续跑时直接补本步
            self._save_checkpoint(checkpoint_key, source_signature, [sections_text], "finalize")
        data = self._chat_json(self._finalize_messages(sections_text, source), purpose="整篇笔记")
        note = normalize_note(data)
        if checkpoint_key:
            self._clear_checkpoint(checkpoint_key)
        return note

    def summarize_note(self, source: GPTSource, progress_cb=None) -> dict:
        """map（分段出小节）→ merge（合并去重）→ finalize（整篇笔记）。

        全程 checkpoint 断点续跑：map / merge / finalize 三个阶段各自落盘，
        中途失败重试不会重复消耗已完成阶段的调用。返回归一化 note_json。
        progress_cb(detail: str, fraction: float) 可选，回报生成进度（0~1）。
        """
        self.screenshot = source.screenshot
        self.link = source.link
        source.segment = self.ensure_segments_type(source.segment)
        checkpoint_key = source.checkpoint_key
        source_signature = self._build_source_signature(source) if checkpoint_key else None

        def message_builder(segments, image_urls, **kwargs):
            return self.create_messages(segments, video_img_urls=image_urls, **kwargs)

        def report(detail: str, fraction: float):
            if progress_cb:
                try:
                    progress_cb(detail, max(0.0, min(1.0, fraction)))
                except Exception:
                    pass

        chunker = RequestChunker(message_builder, self.max_request_bytes, self._estimate_messages_bytes)

        try:
            chunks = chunker.chunk(
                source.segment,
                source.video_img_urls or [],
                title=source.title,
                tags=source.tags,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )
        except ValueError:
            chunks = chunker.chunk(
                source.segment,
                [],
                title=source.title,
                tags=source.tags,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )

        partials: List[str] = []
        phase = "map"
        if checkpoint_key and source_signature:
            checkpoint = self._load_checkpoint(checkpoint_key, source_signature)
            if checkpoint and isinstance(checkpoint.get("partials"), list):
                phase = checkpoint.get("phase") or "map"
                partials = checkpoint["partials"]

        # finalize 断点：合并已完成，直接补最后一步
        if phase == "finalize" and partials:
            report("整篇汇总（断点续跑）", 0.9)
            return self._finalize_note(partials[0], source, checkpoint_key, source_signature)

        # merge 断点：从合并现场继续
        if phase == "merge" and partials:
            report("合并去重（断点续跑）", 0.7)
            merged_text = self._merge_partials(partials, checkpoint_key, source_signature)
            report("整篇汇总", 0.9)
            return self._finalize_note(merged_text, source, checkpoint_key, source_signature)

        if len(partials) > len(chunks):
            partials = []

        total_chunks = max(1, len(chunks))
        for chunk in chunks[len(partials):]:
            messages = self.create_messages(
                chunk.segments,
                title=source.title,
                tags=source.tags,
                video_img_urls=chunk.image_urls,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )
            try:
                data = self._chat_json(messages, purpose="分段小节")
            except Exception:
                if checkpoint_key and source_signature:
                    self._save_checkpoint(checkpoint_key, source_signature, partials, "map")
                raise

            partials.append(self._normalize_sections_text(data))
            report(f"分段总结 {len(partials)}/{total_chunks}", 0.7 * len(partials) / total_chunks)
            if checkpoint_key and source_signature:
                self._save_checkpoint(checkpoint_key, source_signature, partials, "map")

        report("合并去重", 0.7)
        merged_text = self._merge_partials(partials, checkpoint_key, source_signature)
        report("整篇汇总", 0.9)
        return self._finalize_note(merged_text, source, checkpoint_key, source_signature)

    def summarize(self, source: GPTSource) -> str:
        """兼容入口：返回派生 Markdown。

        structured-v1 起 note_json 是源真值，Markdown 由 note_render 派生；
        标记协议（*Content-[mm:ss] / *Screenshot-[mm:ss]）不变，下游后处理照旧。
        """
        from app.gpt.note_render import note_to_markdown

        note = self.summarize_note(source)
        formats = source._format or []
        return note_to_markdown(
            note,
            link='link' in formats,
            screenshot='screenshot' in formats,
            toc='toc' in formats,
            summary='summary' in formats,
        )
