"""markdown-v2 管线回归：Markdown 直出 map → merge → finalize，无 JSON 校验。

背景：structured-v1 的 JSON 结构校验已按需求下线，笔记产物就是纯 Markdown；
本文件锁定新管线的三个关键行为：
1. summarize_markdown 全流程（单分段：map + finalize）直接返回最终 Markdown；
2. 空输出会被回喂重试，不会把空串当笔记落盘；
3. 多分段 merge 把各段 Markdown 合并后再进入 finalize。
"""
import unittest
from types import SimpleNamespace

from app.gpt.universal_gpt import UniversalGPT

MAP_MD = "### 小节标题 *Content-[00:00:01]\n\n小节正文。"
MERGE_MD = "### 合并小节 *Content-[00:00:01]\n\n合并后的正文。"
FINAL_MD = "# 笔记标题\n\n> 概述\n\n## 1. 章节\n\n正文"


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class FakeClient:
    """按脚本回放 chat.completions.create 的返回文本。"""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0
        outer = self

        class _Completions:
            def create(self, **_kwargs):
                outer.calls += 1
                return _response(outer.outputs.pop(0))

        self.chat = SimpleNamespace(completions=_Completions())


def _source():
    return SimpleNamespace(
        title="视频标题",
        tags=["标签"],
        segment=[{"start": 0.0, "end": 10.0, "text": "转写内容"}],
        screenshot=False,
        video_img_urls=[],
        link=True,
        _format=["link"],
        style=None,
        extras=None,
        checkpoint_key=None,
    )


class SummarizeMarkdownTest(unittest.TestCase):
    def _gpt(self, outputs):
        return UniversalGPT(client=FakeClient(outputs), model="test-model")

    def test_full_flow_returns_final_markdown(self):
        """单分段：map 一次 + finalize 一次，返回 finalize 的 Markdown 原文。"""
        gpt = self._gpt([MAP_MD, FINAL_MD])
        md = gpt.summarize_markdown(_source())
        self.assertEqual(md, FINAL_MD)
        self.assertEqual(gpt.client.calls, 2)

    def test_empty_output_is_retried(self):
        """空输出回喂重试，成功后正常返回；连续空则报错而不是落盘空笔记。"""
        gpt = self._gpt(["", MAP_MD, FINAL_MD])
        md = gpt.summarize_markdown(_source())
        self.assertEqual(md, FINAL_MD)

        gpt_all_empty = self._gpt(["", "", ""])
        with self.assertRaises(ValueError):
            gpt_all_empty.summarize_markdown(_source())
        self.assertEqual(gpt_all_empty.client.calls, 3)

    def test_merge_partials_concatenates_then_finalizes(self):
        """多分段：merge 把各段 Markdown 合并后才进入 finalize。"""
        gpt = self._gpt([MERGE_MD, FINAL_MD])
        merged = gpt._merge_partials([MAP_MD, MAP_MD + " 二"], None, None)
        self.assertEqual(merged, MERGE_MD)
        self.assertEqual(gpt.client.calls, 1)

        md = gpt._finalize_markdown(merged, _source())
        self.assertEqual(md, FINAL_MD)

    def test_finalize_messages_carry_title_and_sections(self):
        gpt = self._gpt([])
        messages = gpt._finalize_messages(MAP_MD, _source())
        content = messages[0]["content"]
        self.assertIn("视频标题", content)
        self.assertIn(MAP_MD, content)
        self.assertIn("Markdown", content)


if __name__ == "__main__":
    unittest.main()
