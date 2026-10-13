"""导出层（P3）：Markdown 笔记 → 打印友好 HTML。

只做 HTML + Markdown 两种格式（无 Pandoc / headless 浏览器等外部依赖）。
HTML 内嵌轻量样式并用 KaTeX CDN 渲染 $...$ 公式，浏览器直接打印即可成 PDF。
（自测 / 错题 / 复习资料功能已下线，复习资料渲染随之移除。）
"""
import html
import re
from typing import List

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
@media print { body { margin: 0 auto; } h2 { page-break-after: avoid; } }
"""


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"zh\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>{html.escape(title)}</title>\n"
        f"{_KATEX_CDN}\n<style>{_PAGE_STYLE}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


# ---------------------------------------------------------------- 单篇笔记

def _inline_md_html(text: str) -> str:
    """行内 Markdown → HTML：图片/链接先抽占位，转义后回填，再处理加粗/行内代码/斜体。"""
    stash: List[str] = []

    def _keep(html_str: str) -> str:
        stash.append(html_str)
        return f"\x00{len(stash) - 1}\x00"

    t = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        lambda m: _keep(f'<img src="{html.escape(m.group(2), quote=True)}" alt="{html.escape(m.group(1))}" style="max-width:100%"/>'),
        text or "",
    )
    t = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: _keep(f'<a href="{html.escape(m.group(2), quote=True)}">{html.escape(m.group(1))}</a>'),
        t,
    )
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], t)
    return t


def _table_cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def markdown_to_html(markdown: str, title: str = "视频笔记") -> str:
    """Markdown 正文 → 打印友好 HTML（CommonMark 常用子集 + GFM 表格）。

    公式 $...$ / $$...$$ 原样保留，交给页面里的 KaTeX auto-render 渲染。
    """
    lines = (markdown or "").splitlines()
    body: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        stripped = lines[i].strip()

        # 围栏代码块
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            code: List[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{html.escape(lang)}"' if lang else ""
            body.append(f"<pre><code{cls}>{html.escape(chr(10).join(code))}</code></pre>")
            continue

        if not stripped:
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)), 6)
            body.append(f"<h{level}>{_inline_md_html(m.group(2))}</h{level}>")
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            quote: List[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            body.append("<blockquote>" + "<br/>".join(_inline_md_html(q) for q in quote if q) + "</blockquote>")
            continue

        # GFM 表格：当前行是 | ... | 且下一行是分隔行
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            headers = _table_cells(stripped)
            i += 2
            rows: List[List[str]] = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_table_cells(lines[i]))
                i += 1
            head = "".join(f"<th>{_inline_md_html(h)}</th>" for h in headers)
            body_rows = "".join(
                "<tr>" + "".join(f"<td>{_inline_md_html(c)}</td>" for c in row) + "</tr>" for row in rows
            )
            body.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body_rows}</tbody></table>")
            continue

        # 分隔线
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            body.append("<hr/>")
            i += 1
            continue

        # 列表（连续同类项合并为一个列表；缩进子项拍平）
        if re.match(r"^[-*+]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped):
            ordered = bool(re.match(r"^\d+[.)]\s+", stripped))
            tag = "ol" if ordered else "ul"
            pat = r"^\d+[.)]\s+" if ordered else r"^[-*+]\s+"
            items: List[str] = []
            while i < n and re.match(pat, lines[i].strip()):
                items.append(_inline_md_html(re.sub(pat, "", lines[i].strip())))
                i += 1
            body.append(f"<{tag}>" + "".join(f"<li>{it}</li>" for it in items) + f"</{tag}>")
            continue

        # 段落：连续普通行合并
        para: List[str] = []
        while i < n:
            s = lines[i].strip()
            if (not s or s.startswith("#") or s.startswith(">") or s.startswith("|")
                    or s.startswith("```") or re.match(r"^[-*+]\s+", s) or re.match(r"^\d+[.)]\s+", s)):
                break
            para.append(s)
            i += 1
        if para:
            body.append("<p>" + "<br/>".join(_inline_md_html(p) for p in para) + "</p>")

    return _page(title, "\n".join(body))
