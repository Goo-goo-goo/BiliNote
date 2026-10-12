"""自测题归一化与本地判分单元测试（P2）。"""
import unittest

from app.services.quiz_generator import (
    grade_question,
    judge_fill,
    normalize_fill_answer,
    normalize_judge_answer,
    normalize_question,
    normalize_single_answer,
    split_fill_blanks,
)


class TestAnswerNormalize(unittest.TestCase):
    def test_single_letter_variants(self):
        self.assertEqual(normalize_single_answer("A"), "A")
        self.assertEqual(normalize_single_answer("b)"), "B")
        self.assertEqual(normalize_single_answer("C。"), "C")
        self.assertEqual(normalize_single_answer(""), "")

    def test_single_by_option_text(self):
        options = ["牛顿", "爱因斯坦", "伽利略", "麦克斯韦"]
        self.assertEqual(normalize_single_answer("爱因斯坦", options), "B")

    def test_judge_words(self):
        self.assertEqual(normalize_judge_answer("正确"), "正确")
        self.assertEqual(normalize_judge_answer("对"), "正确")
        self.assertEqual(normalize_judge_answer("√"), "正确")
        self.assertEqual(normalize_judge_answer("false"), "错误")
        self.assertEqual(normalize_judge_answer("错的"), "错误")
        self.assertEqual(normalize_judge_answer("不知道"), "")

    def test_fill_normalize(self):
        self.assertEqual(normalize_fill_answer("牛顿 / Newton | 3"), "牛顿 / newton | 3")
        self.assertEqual(normalize_fill_answer(["第一空，", " 第二空 "]), "第一空 | 第二空")
        # 等价答案去重且保序
        self.assertEqual(normalize_fill_answer("A / a / A | b"), "a | b")

    def test_split_fill_blanks(self):
        self.assertEqual(split_fill_blanks("____ 是谁？"), 1)
        self.assertEqual(split_fill_blanks("____ 与 ____ 的关系"), 2)
        self.assertEqual(split_fill_blanks("没有空位"), 1)


class TestJudgeFill(unittest.TestCase):
    def test_all_correct(self):
        ok, per = judge_fill("牛顿 / newton | 3", ["牛顿", "3"])
        self.assertTrue(ok)
        self.assertEqual(per, [True, True])

    def test_equivalent_answer(self):
        ok, per = judge_fill("牛顿 / newton | 3", "Newton | 3")
        self.assertTrue(ok)

    def test_partial_wrong(self):
        ok, per = judge_fill("牛顿 / newton | 3", ["牛顿", "4"])
        self.assertFalse(ok)
        self.assertEqual(per, [True, False])

    def test_missing_blank_is_wrong(self):
        ok, per = judge_fill("a | b", ["a"])
        self.assertFalse(ok)
        self.assertEqual(per, [True, False])


class TestNormalizeQuestion(unittest.TestCase):
    def test_fill_detected_by_blank(self):
        q = normalize_question({"type": "x", "stem": "____ 是惯性定律", "answer": "牛顿 / Newton"})
        self.assertEqual(q["qtype"], "fill")
        self.assertEqual(q["answer"], "牛顿 / newton")

    def test_judge_detected_by_stem(self):
        self.assertEqual(normalize_question({"stem": "判断：地球是平的", "answer": "错误"})["qtype"], "judge")

    def test_single_with_options(self):
        q = normalize_question({"type": "single", "stem": "1+1=?", "options": ["1", "2", "3", "4"], "answer": "B."})
        self.assertEqual(q["qtype"], "single")
        self.assertEqual(q["answer"], "B")

    def test_calc_fallback(self):
        self.assertEqual(normalize_question({"type": "proof", "stem": "证明...", "answer": "略"})["qtype"], "calc")

    def test_empty_stem_dropped(self):
        self.assertIsNone(normalize_question({"stem": "", "answer": "A"}))


class TestGradeQuestion(unittest.TestCase):
    def _q(self, **kw):
        base = {"qtype": "single", "difficulty": "basic", "stem": "s", "options": ["a", "b", "c", "d"],
                "answer": "B", "explanation": "", "knowledge_point": "", "time_stamp": ""}
        base.update(kw)
        return base

    def test_single_local_correct(self):
        result = grade_question(self._q(), "b")
        self.assertTrue(result["correct"])
        self.assertEqual(result["graded_by"], "local")

    def test_single_local_wrong(self):
        result = grade_question(self._q(), "A")
        self.assertFalse(result["correct"])
        self.assertIn("B", result["feedback"])

    def test_judge_local(self):
        result = grade_question(self._q(qtype="judge", options=[], answer="正确"), "对")
        self.assertTrue(result["correct"])

    def test_fill_local_with_blank_feedback(self):
        q = self._q(qtype="fill", options=[], answer="牛顿 / Newton | 3", stem="____ 给出 ____")
        result = grade_question(q, ["牛顿", "4"])
        self.assertFalse(result["correct"])
        self.assertIn("第 2 空", result["feedback"])

    def test_calc_exact_match_local(self):
        q = self._q(qtype="calc", options=[], answer="42")
        result = grade_question(q, " 42 ")
        self.assertTrue(result["correct"])
        self.assertEqual(result["graded_by"], "local")

    def test_calc_without_gpt_is_ungraded(self):
        q = self._q(qtype="calc", options=[], answer="42")
        result = grade_question(q, "43", gpt=None)
        self.assertIsNone(result["correct"])
        self.assertEqual(result["graded_by"], "none")

    def test_calc_with_gpt_uses_ai(self):
        q = self._q(qtype="calc", options=[], answer="x=2")

        class _FakeGPT:
            def chat_json(self, messages, purpose=""):
                return {"correct": True, "feedback": "解法正确"}

        result = grade_question(q, "x=2 是解", gpt=_FakeGPT())
        self.assertTrue(result["correct"])
        self.assertEqual(result["graded_by"], "ai")


if __name__ == "__main__":
    unittest.main()
