"""导出层单元测试（P3）：Markdown → HTML 渲染。"""
import unittest

from app.utils.note_export import markdown_to_html

MD_NOTE = """# 笔记 <x>

> 概述 **加粗**

## 1. 章节 *Content-[00:00:01]

正文段落，含 `code` 与 $E=mc^2$。

1. 一
2. 二

| a | b |
| --- | --- |
| 1 | 2 |

```python
print(1)
```

### 1.1 小节

- 要点

---
"""


class TestMarkdownHtml(unittest.TestCase):
    def test_blocks_rendered(self):
        page = markdown_to_html(MD_NOTE, title="标题")
        self.assertIn("<h1>笔记 &lt;x&gt;</h1>", page)
        self.assertIn("<blockquote>", page)
        self.assertIn("<strong>加粗</strong>", page)
        self.assertIn("<ol><li>一</li><li>二</li></ol>", page)
        self.assertIn("<table>", page)
        self.assertIn("<pre><code", page)
        self.assertIn("print(1)", page)
        self.assertIn("<ul><li>要点</li></ul>", page)
        self.assertIn("<hr/>", page)
        self.assertIn("$E=mc^2$", page)  # 公式原样保留给 KaTeX

    def test_escapes_injected_markup(self):
        page = markdown_to_html("# 标题\n\n<script>alert(1)</script>\n")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_links_and_images(self):
        page = markdown_to_html("看 [官网](https://example.com) 与 ![图](/static/a.png)")
        self.assertIn('<a href="https://example.com">官网</a>', page)
        self.assertIn('<img src="/static/a.png"', page)


if __name__ == "__main__":
    unittest.main()
