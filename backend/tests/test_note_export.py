"""导出层单元测试（P3）：Markdown / HTML 渲染。"""
import unittest

from app.utils.note_export import note_to_html, review_to_html, review_to_markdown

REVIEW = {
    "title": "复习资料",
    "summary": "核心结论",
    "goals": ["目标1"],
    "chapters": [
        {"title": "章1", "intro": "导读",
         "sections": [{"heading": "节1", "content": "内容 **加粗** 与 $E=mc^2$"}],
         "exercises": [
             {"qtype": "single", "difficulty": "basic", "stem": "1+1=?", "options": ["1", "2", "3", "4"],
              "answer": "B", "explanation": "加法", "knowledge_point": "", "time_stamp": ""},
             {"qtype": "fill", "difficulty": "basic", "stem": "____ 是答案", "options": [],
              "answer": "42", "explanation": "", "knowledge_point": "", "time_stamp": ""},
         ]},
    ],
    "confusions": [{"pair": "A vs B", "difference": "区别"}],
    "glossary": [{"term": "术语", "meaning": "释义"}],
    "cards": [{"front": "问", "back": "答"}],
}

NOTE = {
    "title": "笔记 <x>",
    "summary": "概述",
    "chapters": [{"title": "章", "time_stamp": "", "intro": "",
                  "sections": [{"type": "detail", "heading": "节", "time_stamp": "", "important": True,
                                "blocks": [
                                    {"type": "text", "content": "正文"},
                                    {"type": "steps", "items": ["一", "二"]},
                                    {"type": "code", "language": "python", "content": "print(1)"},
                                    {"type": "table", "headers": ["a", "b"], "rows": [["1", "2"]]},
                                ]}],
                  "summary": "小结", "key_points": ["要点"]}],
    "key_takeaways": ["结论"],
    "tags": ["tag"],
}


class TestReviewMarkdown(unittest.TestCase):
    def test_full_structure(self):
        md = review_to_markdown(REVIEW)
        self.assertIn("# 复习资料", md)
        self.assertIn("## 学习目标", md)
        self.assertIn("### 章节测试", md)
        self.assertIn("## 易混辨析", md)
        self.assertIn("## 术语索引", md)
        self.assertIn("## 速记卡", md)
        self.assertIn("## 参考答案", md)
        self.assertIn("（单选）1+1=?", md)
        self.assertIn("第 1 章第 2 题", md)


class TestReviewHtml(unittest.TestCase):
    def test_html_page_and_escaping(self):
        page = review_to_html(REVIEW)
        self.assertIn("<!DOCTYPE html>", page)
        self.assertIn("katex", page)
        self.assertIn("章节测试", page)
        self.assertIn("易混辨析", page)
        self.assertIn("速记卡", page)

    def test_html_escapes_injected_markup(self):
        evil = {"title": "<script>alert(1)</script>", "summary": "", "goals": [],
                "chapters": [{"title": "c", "intro": "", "sections": [{"heading": "<b>x</b>", "content": ""}],
                              "exercises": []}], "confusions": [], "glossary": [], "cards": []}
        page = review_to_html(evil)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)


class TestNoteHtml(unittest.TestCase):
    def test_note_blocks_rendered(self):
        page = note_to_html(NOTE)
        self.assertIn("<h1>笔记 &lt;x&gt;</h1>", page)
        self.assertIn("<ol><li>一</li><li>二</li></ol>", page)
        self.assertIn("print(1)", page)
        self.assertIn("<table>", page)
        self.assertIn("⭐", page)
        self.assertIn("核心要点", page)


if __name__ == "__main__":
    unittest.main()
