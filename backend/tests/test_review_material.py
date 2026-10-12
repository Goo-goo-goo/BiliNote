"""复习资料生成单元测试（P3）：蒸馏、大纲映射、详/简版流程（假 GPT）。"""
import unittest

from app.services.review_material import (
    assemble_material,
    distill_note,
    generate_review_material,
    plan_chapters,
)

NOTE = {
    "title": "笔记A",
    "summary": "概述A",
    "chapters": [
        {"title": "章1", "time_stamp": "00:01:00", "intro": "",
         "sections": [{"type": "detail", "heading": "小节1", "time_stamp": "00:01:00",
                       "important": False, "blocks": [{"type": "text", "content": "正文"}]}],
         "summary": "小结", "key_points": ["要点1"]},
    ],
    "key_takeaways": ["结论1"],
    "tags": ["t"],
}

CHAPTER_RAW = {"chapter": {"title": "章A", "intro": "导读",
                           "sections": [{"heading": "节", "content": "内容"}],
                           "exercises": [{"type": "judge", "stem": "判断题干", "answer": "正确"}]}}


class _FakeGPT:
    """按调用顺序返回预置 JSON 的假 GPT。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_json(self, messages, purpose=""):
        self.calls.append(purpose)
        return self.responses.pop(0)


class TestDistill(unittest.TestCase):
    def test_distill_note_keeps_structure_but_drops_body(self):
        d = distill_note(NOTE, "task-1", 0)
        self.assertEqual(d["task_id"], "task-1")
        self.assertEqual(d["index"], 0)
        self.assertEqual(d["chapters"][0]["section_headings"], ["小节1"])
        self.assertNotIn("blocks", str(d))


class TestPlanChapters(unittest.TestCase):
    def test_plan_maps_episode_refs(self):
        digest = [distill_note(NOTE, "t1", 0), distill_note(NOTE, "t2", 1)]
        outline = {"chapters": [{"title": "章X", "goal": "g", "episode_refs": [1]}]}
        plans = plan_chapters(outline, digest)
        self.assertEqual(len(plans), 1)
        self.assertEqual([e["task_id"] for e in plans[0]["episodes"]], ["t2"])

    def test_plan_fallback_without_refs(self):
        digest = [distill_note(NOTE, "t1", 0), distill_note(NOTE, "t2", 1)]
        outline = {"chapters": [{"title": "章X", "episode_refs": [99]}]}
        plans = plan_chapters(outline, digest)
        self.assertEqual(len(plans[0]["episodes"]), 2)

    def test_plan_caps_chapters(self):
        digest = [distill_note(NOTE, "t1", 0)]
        outline = {"chapters": [{"title": f"章{i}"} for i in range(20)]}
        plans = plan_chapters(outline, digest, max_chapters=5)
        self.assertEqual(len(plans), 5)
        self.assertEqual(plans[-1]["title"], "其他要点")

    def test_empty_outline_gets_default_chapter(self):
        self.assertEqual(plan_chapters({}, [distill_note(NOTE, "t", 0)])[0]["title"], "核心内容")


class TestAssemble(unittest.TestCase):
    def test_assemble_material(self):
        content = assemble_material(
            {"summary": "总", "goals": ["目标"], "confusions": [{"pair": "A vs B", "difference": "d"}],
             "glossary": [{"term": "T", "meaning": "M"}], "cards": [{"front": "F", "back": "B"}]},
            [{"title": "章"}], "资料",
        )
        self.assertEqual(content["title"], "资料")
        self.assertEqual(content["confusions"][0]["pair"], "A vs B")
        self.assertEqual(content["glossary"][0]["term"], "T")
        self.assertEqual(content["cards"][0]["front"], "F")


class TestGenerate(unittest.TestCase):
    def test_full_mode_three_steps(self):
        gpt = _FakeGPT([
            {"chapters": [{"title": "章X", "episode_refs": [0]}]},  # ① 大纲
            CHAPTER_RAW,                                          # ② 逐章
            {"summary": "总", "goals": ["g"], "confusions": [], "glossary": [], "cards": []},  # ③ 总览
        ])
        progress = []
        content = generate_review_material(
            material_id=1, title="资料", notes=[NOTE], task_ids=["t1"], gpt=gpt,
            detail_mode="full", progress_cb=progress.append,
        )
        self.assertEqual(gpt.calls, ["复习大纲", "第1章", "复习总览"])
        self.assertEqual(content["chapters"][0]["title"], "章A")
        self.assertEqual(content["chapters"][0]["exercises"][0]["qtype"], "judge")
        self.assertTrue(any("逐章生成 1/1" in p for p in progress))

    def test_brief_mode_one_call(self):
        gpt = _FakeGPT([{
            "title": "简版", "summary": "s", "goals": [],
            "chapters": [CHAPTER_RAW], "confusions": [], "glossary": [], "cards": [],
        }])
        content = generate_review_material(
            material_id=1, title="资料", notes=[NOTE], task_ids=["t1"], gpt=gpt, detail_mode="brief",
        )
        self.assertEqual(len(gpt.calls), 1)
        self.assertEqual(content["title"], "简版")
        self.assertEqual(len(content["chapters"]), 1)

    def test_no_notes_raises(self):
        with self.assertRaises(ValueError):
            generate_review_material(1, "x", [], [], _FakeGPT([]), "full")


if __name__ == "__main__":
    unittest.main()
