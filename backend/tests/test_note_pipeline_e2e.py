"""笔记生成主链路端到端测试（pipeline: markdown-v2）。

覆盖真实编排代码：状态富文档推进 → 跳下载取元信息 → 转写缓存命中 →
LLM map-reduce（真实 UniversalGPT 编排 + 假 OpenAI 客户端返回预置 Markdown）→
Markdown 直出（无 JSON 校验）→ 链接标记替换 → 落盘 → NoteResult。
只有两个外部依赖是假件：下载器、LLM HTTP 客户端。
"""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.enmus.task_status_enums import TaskStatus
from app.gpt.universal_gpt import UniversalGPT
from app.models.audio_model import AudioDownloadResult
from app.db.init_db import init_db
from app.db.video_task_dao import get_task_by_video
from app.routers.note import save_note_to_file
from app.services import task_status
from app.services.note import NoteGenerator
from app.utils.path_helper import get_note_results_dir

TASK_ID = "e2e-task-1"

MAP_MD = (
    "### ⭐ 核心概念 *Content-[00:00:10]\n\n"
    "这是概念讲解。"
)

FINAL_MD = (
    "# 端到端测试笔记\n\n"
    "> 一句话核心结论。\n\n"
    "## 1. 第一章 *Content-[00:00:10]\n\n"
    "### 1.1 ⭐ 核心概念 *Content-[00:00:10]\n\n"
    "这是概念讲解。\n\n"
    "> **本章小结**：本章小结\n\n"
    "**本章要点**\n\n"
    "- 要点一\n\n"
    "## 核心要点\n\n"
    "- 结论一\n"
    "- 结论二\n"
)


class _FakeCompletions:
    """按提示词内容区分 map / finalize 的假 OpenAI completions。"""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        prompt = json.dumps(kwargs.get("messages", []), ensure_ascii=False)
        content = FINAL_MD if "整理成整篇视频笔记" in prompt else MAP_MD
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())
        self.models = SimpleNamespace(list=lambda: [])


class _FakeDownloader:
    def download(self, **kwargs):
        return AudioDownloadResult(
            file_path="", title="测试视频", duration=120.0, cover_url="",
            platform="bilibili", video_id="BV1xx", raw_info={"tags": ["AI"]},
        )

    def download_subtitles(self, *args, **kwargs):
        return None


class TestNotePipelineE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_full_pipeline(self):
        note_dir = Path(get_note_results_dir())
        note_dir.mkdir(parents=True, exist_ok=True)
        # 转写缓存命中 → 跳过下载音频与转写（不碰 ffmpeg / whisper）
        (note_dir / f"{TASK_ID}_transcript.json").write_text(json.dumps({
            "language": "zh",
            "full_text": "大家好，这是概念的讲解。",
            "segments": [{"start": 8.0, "end": 15.0, "text": "大家好，这是概念的讲解。"}],
        }, ensure_ascii=False), encoding="utf-8")

        # 跳过真实转写器初始化（whisper 模型加载），管线其余部分全走真实代码
        original_init = NoteGenerator._init_transcriber
        NoteGenerator._init_transcriber = lambda self: None
        try:
            generator = NoteGenerator()
        finally:
            NoteGenerator._init_transcriber = original_init

        client = _FakeClient()
        generator._get_gpt = lambda *args, **kw: UniversalGPT(client, "mock-model")
        generator._get_downloader = lambda *args, **kw: _FakeDownloader()

        result = generator.generate(
            video_url="https://www.bilibili.com/video/BV1xx",
            platform="bilibili",
            task_id=TASK_ID,
            link=True,
            screenshot=False,
            _format=["link", "summary"],
            style="detailed",
        )

        # 1) Markdown 直出是源真值（无 note_json）
        self.assertIsNotNone(result)
        md = result.markdown
        self.assertIn("# 端到端测试笔记", md)
        self.assertIn("核心要点", md)
        self.assertIn("这是概念讲解。", md)

        # 2) 时间标记已替换成原片跳转链接
        self.assertNotIn("*Content-", md)
        self.assertIn("原片 @ 00:00:10", md)
        self.assertIn("t=10", md)

        # 3) map-reduce 编排真实发生：至少 1 次 map + 1 次 finalize
        prompts = [json.dumps(c.get("messages", []), ensure_ascii=False)
                   for c in client.chat.completions.calls]
        self.assertTrue(any("Markdown 笔记小节" in p for p in prompts))
        self.assertTrue(any("整理成整篇视频笔记" in p for p in prompts))

        # 4) 状态富文档：完整阶段轨迹 + 终态 + 视频标题
        doc = task_status.read_status(TASK_ID)
        self.assertEqual(doc["title"], "测试视频")  # 列表页据此显示标题而不是 task_id
        self.assertEqual(doc["status"], TaskStatus.SUCCESS.value)
        self.assertTrue(doc["finished"])
        self.assertEqual(doc["step"], 6)
        self.assertEqual(doc["progress"], 1.0)
        history_statuses = [h["status"] for h in doc["history"]]
        self.assertIn("SUMMARIZING", history_statuses)
        self.assertEqual(history_statuses[-1], "SUCCESS")

        # 5) 路由层同款落盘（save_note_to_file）：结果文件只有 markdown/transcript/audio_meta，
        #    checkpoint 已清理；任务记录已写入 DB
        save_note_to_file(TASK_ID, result)
        result_file = note_dir / f"{TASK_ID}.json"
        self.assertTrue(result_file.exists())
        saved = json.loads(result_file.read_text(encoding="utf-8"))
        self.assertIn("# 端到端测试笔记", saved["markdown"])
        self.assertNotIn("note", saved)
        self.assertFalse((note_dir / f"{TASK_ID}.gpt.checkpoint.json").exists())
        self.assertEqual(get_task_by_video("BV1xx", "bilibili"), TASK_ID)


if __name__ == "__main__":
    unittest.main()
