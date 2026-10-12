"""structured-v1 笔记渲染层单元测试：JSON 提取、归一化、Markdown 派生、长视频标记。"""
import json
import unittest

from app.gpt.note_render import (
    extract_json,
    extract_sections,
    normalize_note,
    note_to_markdown,
    parse_timestamp,
    to_marker_time,
    to_hms,
)
from app.utils.note_helper import replace_content_markers
from app.utils.screenshot_marker import extract_screenshot_timestamps


class TestTimestamp(unittest.TestCase):
    def test_parse_hms(self):
        self.assertEqual(parse_timestamp("01:02:03"), 3723)
        self.assertEqual(parse_timestamp("00:12:34"), 754)
        self.assertEqual(parse_timestamp("12:34"), 754)

    def test_parse_invalid(self):
        self.assertIsNone(parse_timestamp("abc"))
        self.assertIsNone(parse_timestamp(None))

    def test_marker_time_is_total_minutes(self):
        self.assertEqual(to_marker_time("01:02:03"), "62:03")
        self.assertEqual(to_marker_time("00:09:05"), "09:05")

    def test_to_hms_roundtrip(self):
        self.assertEqual(to_hms("62:03"), "01:02:03")


class TestExtractJson(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        text = '```json\n{"a": 1}\n```'
        self.assertEqual(extract_json(text), {"a": 1})

    def test_json_after_prose(self):
        text = '好的，以下是结果：\n{"a": 1}\n以上。'
        self.assertEqual(extract_json(text), {"a": 1})

    def test_latex_braces_before_json(self):
        # 模型先解释 LaTeX 再给 JSON：不能被前面的大括号带偏
        text = '用 \\frac{a}{b} 表示分数，结果如下：{"sections": []}'
        self.assertEqual(extract_json(text), {"sections": []})

    def test_truncated_json_hint(self):
        # 没有任何完整子值可提取时，报「疑似被截断」线索
        with self.assertRaises(ValueError) as ctx:
            extract_json('{"sections": [{"a": 1')
        self.assertIn("截断", str(ctx.exception))

    def test_partial_object_falls_back_to_inner_value(self):
        # 外层对象被截断但内层完整时，容忍并取出内层（比整体失败更可用）
        self.assertEqual(extract_json('{"sections": [{"a": 1}]'), [{"a": 1}])

    def test_extract_sections_variants(self):
        self.assertEqual(extract_sections('{"sections": [{"a": 1}]}'), [{"a": 1}])
        self.assertEqual(extract_sections('[{"a": 1}]'), [{"a": 1}])


FULL_NOTE = {
    "title": "测试笔记",
    "summary": "核心结论先行。",
    "chapters": [
        {
            "title": "第一章",
            "time_stamp": "00:01:00",
            "intro": "导读",
            "sections": [
                {
                    "type": "steps",
                    "heading": "操作步骤",
                    "time_stamp": "00:01:05",
                    "important": True,
                    "blocks": [
                        {"type": "steps", "items": ["第一步", "第二步"]},
                        {"type": "code", "language": "python", "content": "print(1)"},
                        {"type": "table", "headers": ["项", "值"], "rows": [["a", "1"]]},
                        {"type": "screenshot", "time_stamp": "00:01:30", "content": "界面演示"},
                    ],
                }
            ],
            "summary": "本章小结",
            "key_points": ["要点1"],
        }
    ],
    "key_takeaways": ["结论1", "结论2"],
    "tags": ["AI", "笔记"],
}


class TestNormalizeNote(unittest.TestCase):
    def test_full_note_kept(self):
        note = normalize_note(FULL_NOTE)
        self.assertEqual(note["title"], "测试笔记")
        self.assertEqual(len(note["chapters"]), 1)
        self.assertEqual(len(note["chapters"][0]["sections"][0]["blocks"]), 4)

    def test_sections_only_wrapped_into_chapter(self):
        note = normalize_note('{"sections": [{"type": "detail", "heading": "小节", "time_stamp": "00:00:10", "blocks": [{"type": "text", "content": "内容"}]}]}')
        self.assertEqual(len(note["chapters"]), 1)
        self.assertEqual(note["chapters"][0]["sections"][0]["heading"], "小节")

    def test_junk_blocks_dropped(self):
        raw = {"title": "x", "chapters": [{"title": "c", "sections": [
            {"type": "detail", "heading": "h", "blocks": [{"type": "text", "content": ""}, {"type": "unknown", "content": "z"}]},
        ]}]}
        note = normalize_note(raw)
        # unknown 块退化为 text 并保留内容；空 text 块被丢弃
        self.assertEqual(len(note["chapters"][0]["sections"][0]["blocks"]), 1)

    def test_empty_note_raises(self):
        with self.assertRaises(ValueError):
            normalize_note('{"chapters": []}')

    def test_fenced_input_accepted(self):
        note = normalize_note('```json\n' + json.dumps(FULL_NOTE, ensure_ascii=False) + '\n```')
        self.assertEqual(note["title"], "测试笔记")


class TestNoteToMarkdown(unittest.TestCase):
    def test_markers_emitted(self):
        md = note_to_markdown(FULL_NOTE, link=True, screenshot=True, toc=True, summary=True)
        self.assertIn("# 测试笔记", md)
        self.assertIn("## 1. 第一章 *Content-[01:00]", md)
        self.assertIn("### 1.1 ⭐ 操作步骤 *Content-[01:05]", md)
        self.assertIn("*Screenshot-[01:30]", md)
        self.assertIn("## 目录", md)
        self.assertIn("## 核心要点", md)
        self.assertIn("## AI 总结", md)
        self.assertIn("> **本章小结**：本章小结", md)

    def test_blocks_rendered(self):
        md = note_to_markdown(FULL_NOTE, link=False, screenshot=False, toc=False, summary=False)
        self.assertIn("1. 第一步", md)
        self.assertIn("```python", md)
        self.assertIn("| 项 | 值 |", md)
        self.assertNotIn("*Content-", md)
        self.assertNotIn("*Screenshot-", md)

    def test_marker_protocol_roundtrip(self):
        """派生 Markdown 的标记必须能被既有后处理管线识别（链接替换 / 截图提取）。"""
        md = note_to_markdown(FULL_NOTE, link=True, screenshot=True, toc=False, summary=False)
        shots = extract_screenshot_timestamps(md)
        self.assertEqual(shots, [("*Screenshot-[01:30]", 90)])
        linked = replace_content_markers(md, video_id="BV1xx", platform="bilibili")
        self.assertNotIn("*Content-[", linked)
        self.assertIn("t=60", linked)
        self.assertIn("t=65", linked)

    def test_long_video_markers(self):
        note = {"title": "长视频", "summary": "", "chapters": [
            {"title": "第二小时", "time_stamp": "01:02:03", "intro": "", "sections": [
                {"type": "detail", "heading": "小节", "time_stamp": "01:02:03", "important": False,
                 "blocks": [{"type": "screenshot", "time_stamp": "01:05:00", "content": ""}]},
            ], "summary": "", "key_points": []},
        ], "key_takeaways": [], "tags": []}
        md = note_to_markdown(note, link=True, screenshot=True)
        self.assertIn("*Content-[62:03]", md)
        self.assertIn("*Screenshot-[65:00]", md)
        self.assertEqual(extract_screenshot_timestamps(md), [("*Screenshot-[65:00]", 3900)])
        linked = replace_content_markers(md, video_id="BV1xx", platform="bilibili")
        self.assertIn("t=3723", linked)
        self.assertNotIn("*Content-", linked)


if __name__ == "__main__":
    unittest.main()
