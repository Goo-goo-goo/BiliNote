"""导出层（P3）：结构化内容 → Markdown / 打印友好 HTML。

只做 HTML + Markdown 两种格式（无 Pandoc / headless 浏览器等外部依赖）。
HTML 内嵌轻量样式并用 KaTeX CDN 渲染 $...$ 公式，浏览器直接打印即可成 PDF。
"""
import html
import re
from typing import List

_QTYPE_LABEL = {"single": "单选", "judge": "判断", "fill": "填空", "calc": "计算/简答"}

_KATEX_CDN = (
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">\n'
    '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>\n'
    '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"\n'
    '        onload="renderMathInElement(document.body, {delimiters:[{left:\'$$\',right:\'$$\',display:true},{left:\'$\',right:\'$\',display:false}]});"></script>'
)

_PAGE_STYLE = """
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
       max-width: 860px; margin: 2rem auto; padding: 0 1.5rem; color: #1f2328; line-height: 1.75; }
h1 { font-size: 1.8rem; border-bottom: 2px solid #d0d7de; padding-bottom: .4rem; }
h2 { font-size: 1.4rem; margin-top: 2rem; border-bottom: 1px solid #d0d7de; padding-bottom: .25rem; }
h3 { font-size: 1.15rem; margin-top: 1.4rem; }
table { border-collapse: collapse; width: 100%; margin: .8rem 0; }
th, td { border: 1px solid #d0d7de; padding: .4rem .6rem; text-align: left; vertical-align: top; }
th { background: #f6f8fa; }
blockquote { border-left: 4px solid #388bfd66; background: #f6f8fa; margin: .8rem 0;
             padding: .5rem .9rem; color: #424a53; border-radius: 0 6px 6px 0; }
code { background: #f0f1f3; padding: .1rem .35rem; border-radius: 4px; font-size: .92em; }
pre { background: #f6f8fa; padding: .8rem 1rem; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
.badge { display: inline-block; background: #eef2f6; color: #3a424b; border-radius: 10px;
         padding: 0 .55em; font-size: .8em; margin-left: .4em; }
.takeaway { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px; padding: .8rem 1.1rem; }
.exercise { border: 1px solid #d0d7de; border-radius: 8px; padding: .7rem 1rem; margin: .7rem 0; }
.answer { color: #1a7f37; font-weight: 600; }
.card-table td:first-child { width: 34%; font-weight: 600; }
@media print { body { margin: 0 auto; } h2 { page-break-after: avoid; } .exercise { page-break-inside: avoid; } }
"""


# ---------------------------------------------------------------- 文本

def _inline_html(text: str) -> str:
    """最小内联 Markdown → HTML：转义 + **加粗** + `code`，$公式$原样留给 KaTeX。"""
    out = html.escape(text or "")
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def _inline_md(text: str) -> str:
    return text or ""


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"zh\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>{html.escape(title)}</title>\n"
        f"{_KATEX_CDN}\n<style>{_PAGE_STYLE}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


# ---------------------------------------------------------------- 复习资料

def review_to_markdown(content: dict) -> str:
    lines: List[str] = [f"# {content.get('title') or '复习资料'}", ""]
    if content.get("summary"):
        lines += [content["summary"], ""]
    if content.get("goals"):
        lines += ["## 学习目标", ""]
        lines += [f"- {g}" for g in content["goals"]]
        lines.append("")

    for i, ch in enumerate(content.get("chapters") or [], start=1):
        lines += [f"## {i}. {ch.get('title', '')}", ""]
        if ch.get("intro"):
            lines += [f"> {ch['intro']}", ""]
        for sec in ch.get("sections") or []:
            lines += [f"### {sec.get('heading', '')}", ""]
            lines += [_inline_md(sec.get("content", "")), ""]
        exercises = ch.get("exercises") or []
        if exercises:
            lines += ["### 章节测试", ""]
            for j, q in enumerate(exercises, start=1):
                label = _QTYPE_LABEL.get(q.get("qtype"), "题目")
                lines.append(f"{j}. （{label}）{q.get('stem', '')}")
                for opt in q.get("options") or []:
                    lines.append(f"   - {opt}")
            lines.append("")

    if content.get("confusions"):
        lines += ["## 易混辨析", ""]
        lines += ["| 易混点 | 辨析 |", "| --- | --- |"]
        lines += [f"| {c.get('pair', '')} | {c.get('difference', '')} |" for c in content["confusions"]]
        lines.append("")

    if content.get("glossary"):
        lines += ["## 术语索引", ""]
        lines += ["| 术语 | 释义 |", "| --- | --- |"]
        lines += [f"| {t.get('term', '')} | {t.get('meaning', '')} |" for t in content["glossary"]]
        lines.append("")

    if content.get("cards"):
        lines += ["## 速记卡", ""]
        lines += ["| 正面 | 背面 |", "| --- | --- |"]
        lines += [f"| {c.get('front', '')} | {c.get('back', '')} |" for c in content["cards"]]
        lines.append("")

    # 答案与解析
    answered = [(i + 1, j + 1, q) for i, ch in enumerate(content.get("chapters") or [])
                for j, q in enumerate(ch.get("exercises") or [])]
    if answered:
        lines += ["## 参考答案", ""]
        for ci, qi, q in answered:
            lines.append(f"- 第 {ci} 章第 {qi} 题：**{q.get('answer', '')}**"
                         + (f"（{q.get('explanation', '')}）" if q.get("explanation") else ""))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _exercise_html(q: dict) -> str:
    label = _QTYPE_LABEL.get(q.get("qtype"), "题目")
    parts = [f'<div class="exercise"><p><span class="badge">{label}</span> {_inline_html(q.get("stem", ""))}</p>']
    if q.get("options"):
        opts = "".join(f"<li>{_inline_html(o)}</li>" for o in q["options"])
        parts.append(f"<ol>{opts}</ol>")
    answer = _inline_html(q.get("answer", ""))
    explanation = _inline_html(q.get("explanation", ""))
    parts.append(f'<p class="answer">答案：{answer}</p>')
    if explanation:
        parts.append(f"<p>解析：{explanation}</p>")
    parts.append("</div>")
    return "\n".join(parts)


def review_to_html(content: dict) -> str:
    body: List[str] = [f"<h1>{_inline_html(content.get('title') or '复习资料')}</h1>"]
    if content.get("summary"):
        body.append(f"<blockquote>{_inline_html(content['summary'])}</blockquote>")
    if content.get("goals"):
        body.append("<h2>学习目标</h2><ul>" + "".join(f"<li>{_inline_html(g)}</li>" for g in content["goals"]) + "</ul>")

    for i, ch in enumerate(content.get("chapters") or [], start=1):
        body.append(f"<h2>{i}. {_inline_html(ch.get('title', ''))}</h2>")
        if ch.get("intro"):
            body.append(f"<blockquote>{_inline_html(ch['intro'])}</blockquote>")
        for sec in ch.get("sections") or []:
            body.append(f"<h3>{_inline_html(sec.get('heading', ''))}</h3>")
            for para in re.split(r"\n{2,}", sec.get("content", "") or ""):
                if para.strip():
                    body.append(f"<p>{_inline_html(para.strip())}</p>")
        exercises = ch.get("exercises") or []
        if exercises:
            body.append("<h3>章节测试</h3>")
            body.extend(_exercise_html(q) for q in exercises)

    def _table(headers: List[str], rows: List[List[str]], css: str = "") -> str:
        head = "".join(f"<th>{h}</th>" for h in headers)
        body_rows = "".join("<tr>" + "".join(f"<td>{_inline_html(c)}</td>" for c in row) + "</tr>" for row in rows)
        return f'<table class="{css}"><thead><tr>{head}</tr></thead><tbody>{body_rows}</tbody></table>'

    if content.get("confusions"):
        body.append("<h2>易混辨析</h2>")
        body.append(_table(["易混点", "辨析"], [[c.get("pair", ""), c.get("difference", "")] for c in content["confusions"]]))
    if content.get("glossary"):
        body.append("<h2>术语索引</h2>")
        body.append(_table(["术语", "释义"], [[t.get("term", ""), t.get("meaning", "")] for t in content["glossary"]]))
    if content.get("cards"):
        body.append("<h2>速记卡</h2>")
        body.append(_table(["正面", "背面"], [[c.get("front", ""), c.get("back", "")] for c in content["cards"]], css="card-table"))

    return _page(content.get("title") or "复习资料", "\n".join(body))


# ---------------------------------------------------------------- 单篇笔记

def note_to_html(note: dict, markdown_hint: str = "") -> str:
    """note_json → HTML。markdown_hint 仅用于无章节时的兜底文本展示。"""
    body: List[str] = [f"<h1>{_inline_html(note.get('title') or '视频笔记')}</h1>"]
    if note.get("summary"):
        body.append(f"<blockquote>{_inline_html(note['summary'])}</blockquote>")
    if note.get("tags"):
        body.append("<p>" + " ".join(f'<span class="badge">{_inline_html(t)}</span>' for t in note["tags"]) + "</p>")

    for i, ch in enumerate(note.get("chapters") or [], start=1):
        body.append(f"<h2>{i}. {_inline_html(ch.get('title', ''))}</h2>")
        if ch.get("intro"):
            body.append(f"<p><em>{_inline_html(ch['intro'])}</em></p>")
        for j, sec in enumerate(ch.get("sections") or [], start=1):
            star = "⭐ " if sec.get("important") else ""
            body.append(f"<h3>{star}{i}.{j} {_inline_html(sec.get('heading', ''))}</h3>")
            for block in sec.get("blocks") or []:
                btype = block.get("type")
                if btype == "text":
                    body.append(f"<p>{_inline_html(block.get('content', ''))}</p>")
                elif btype == "formula":
                    body.append(f"<p>$$\n{html.escape(block.get('content', ''))}\n$$</p>")
                elif btype == "quote":
                    body.append(f"<blockquote>{_inline_html(block.get('content', ''))}</blockquote>")
                elif btype in ("steps", "list"):
                    tag = "ol" if (btype == "steps" or block.get("ordered")) else "ul"
                    items = "".join(f"<li>{_inline_html(x)}</li>" for x in block.get("items") or [])
                    body.append(f"<{tag}>{items}</{tag}>")
                elif btype == "code":
                    body.append(f"<pre><code>{html.escape(block.get('content', ''))}</code></pre>")
                elif btype == "table":
                    headers = block.get("headers") or []
                    head = "".join(f"<th>{_inline_html(h)}</th>" for h in headers)
                    rows = "".join("<tr>" + "".join(f"<td>{_inline_html(c)}</td>" for c in row) + "</tr>"
                                   for row in block.get("rows") or [])
                    body.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")
                elif btype == "screenshot":
                    if block.get("image_url"):
                        body.append(f'<figure><img src="{html.escape(block["image_url"])}" alt="截图" style="max-width:100%"/>'
                                    + (f"<figcaption>{_inline_html(block.get('content', ''))}</figcaption>" if block.get("content") else "")
                                    + "</figure>")
                    elif block.get("content"):
                        body.append(f"<p><em>{_inline_html(block['content'])}</em></p>")
        if ch.get("summary"):
            body.append(f"<blockquote><strong>本章小结：</strong>{_inline_html(ch['summary'])}</blockquote>")
        if ch.get("key_points"):
            body.append("<p><strong>本章要点</strong></p><ul>"
                        + "".join(f"<li>{_inline_html(p)}</li>" for p in ch["key_points"]) + "</ul>")

    if note.get("key_takeaways"):
        body.append('<div class="takeaway"><h2>核心要点</h2><ul>'
                    + "".join(f"<li>{_inline_html(p)}</li>" for p in note["key_takeaways"]) + "</ul></div>")

    if len(body) == 1 and markdown_hint:
        body.append(f"<pre>{html.escape(markdown_hint)}</pre>")

    return _page(note.get("title") or "视频笔记", "\n".join(body))
