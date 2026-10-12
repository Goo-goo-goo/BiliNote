"""结构化笔记（note_json）的解析、归一化与 Markdown 派生（pipeline: structured-v1）。

note_json 是源真值；Markdown 由本模块派生，且**沿用既有标记协议**：
  - `*Content-[mm:ss]`    → 由 note_helper.replace_content_markers 换成原片跳转链接
  - `*Screenshot-[mm:ss]` → 由 screenshot_marker / NoteGenerator._insert_screenshots 换成截图
这样截图插入、链接替换、RAG 索引、markmap 思维导图等下游管线一行都不用改。

纯函数模块：不依赖网络、数据库与全局状态，方便单测。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# 小节类型（内容驱动，非教学法预设）
SECTION_TYPES = {
    "overview", "detail", "steps", "example", "comparison", "code", "formula", "conclusion",
}
# 内容块类型
BLOCK_TYPES = {"text", "formula", "steps", "list", "code", "table", "quote", "screenshot"}

_TS_RE = re.compile(r"^(?:(\d{1,3}):)?(\d{1,3}):(\d{2})$")


# ---------------------------------------------------------------- 时间戳

def parse_timestamp(value: Any) -> Optional[int]:
    """HH:MM:SS / MM:SS → 秒数；无法解析返回 None。"""
    if isinstance(value, (int, float)):
        return int(value) if value >= 0 else None
    if not isinstance(value, str):
        return None
    m = _TS_RE.match(value.strip())
    if not m:
        return None
    hh = int(m.group(1) or 0)
    mm = int(m.group(2))
    ss = int(m.group(3))
    return hh * 3600 + mm * 60 + ss


def to_marker_time(value: Any) -> str:
    """任意时间表示 → 标记协议用的 mm:ss（总分钟，可 3 位）。失败返回空串。"""
    seconds = parse_timestamp(value)
    if seconds is None:
        return ""
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def to_hms(value: Any) -> str:
    """任意时间表示 → 规范 HH:MM:SS。失败返回空串。"""
    seconds = parse_timestamp(value)
    if seconds is None:
        return ""
    hh, rem = divmod(seconds, 3600)
    mm, ss = divmod(rem, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


# ---------------------------------------------------------------- JSON 提取

def _strip_code_fence(text: str) -> str:
    t = (text or "").strip()
    fence = chr(96) * 3
    lines = t.split("\n")
    if lines and lines[0].strip().startswith(fence):
        lines = lines[1:]
    if lines and lines[-1].strip() == fence:
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json(text: Any) -> Any:
    """从模型回复里稳健地取出 JSON。

    容忍三种常见噪声：Markdown 代码围栏、JSON 前后的说明散文、正文里先出现的
    LaTeX 大括号。逐个候选起点用 JSONDecoder.raw_decode 尝试，而不是只认第一个
    { 或 [。失败时报出「疑似被截断」等线索，方便上层决定重试还是报错。
    """
    if isinstance(text, (dict, list)):
        return text
    if not isinstance(text, str):
        raise ValueError(f"无法解析 JSON：输入类型 {type(text).__name__}")

    cleaned = _strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(cleaned):
        if ch not in "{[":
            continue
        try:
            value, _end = decoder.raw_decode(cleaned[idx:])
            return value
        except Exception:
            continue

    stripped = cleaned.strip()
    hint = f"（返回 {len(stripped)} 字"
    if stripped.count("{") > stripped.count("}") or stripped.count("[") > stripped.count("]"):
        hint += "，括号未闭合，疑似被截断"
    hint += "）"
    raise ValueError("未找到合法 JSON" + hint)


def extract_sections(raw: Any) -> List[dict]:
    """从 map/merge 产物中取出小节列表；兼容 {"sections": [...]} 与裸数组。"""
    data = extract_json(raw)
    if isinstance(data, dict):
        data = data.get("sections") or data.get("chapters") or []
    if not isinstance(data, list):
        return []
    return [s for s in data if isinstance(s, dict)]


# ---------------------------------------------------------------- 归一化

def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _clean_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [v for v in (_clean_str(item) for item in value) if v]


def normalize_block(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    btype = _clean_str(raw.get("type")).lower() or "text"
    if btype not in BLOCK_TYPES:
        btype = "text"

    if btype in ("text", "formula", "quote"):
        content = _clean_str(raw.get("content"))
        if not content:
            return None
        return {"type": btype, "content": content}

    if btype == "code":
        content = _clean_str(raw.get("content") or raw.get("code"))
        if not content:
            return None
        return {"type": "code", "language": _clean_str(raw.get("language")) or "text", "content": content}

    if btype in ("steps", "list"):
        items = _clean_list(raw.get("items"))
        if not items:
            return None
        block = {"type": btype, "items": items}
        if btype == "list":
            block["ordered"] = bool(raw.get("ordered"))
        return block

    if btype == "table":
        headers = _clean_list(raw.get("headers"))
        rows_raw = raw.get("rows")
        rows: List[List[str]] = []
        if isinstance(rows_raw, list):
            for row in rows_raw:
                if isinstance(row, list):
                    cells = [_clean_str(c) for c in row]
                    if any(cells):
                        rows.append(cells)
        if not headers and not rows:
            return None
        width = len(headers) if headers else max((len(r) for r in rows), default=0)
        if not headers:
            headers = [f"列{i + 1}" for i in range(width)]
        rows = [(r + [""] * width)[:width] for r in rows]
        return {"type": "table", "headers": headers, "rows": rows}

    # screenshot
    content = _clean_str(raw.get("content") or raw.get("caption"))
    ts = to_hms(raw.get("time_stamp"))
    if not ts:
        return None
    block = {"type": "screenshot", "time_stamp": ts}
    if content:
        block["content"] = content
    return block


def normalize_section(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    blocks_raw = raw.get("blocks")
    blocks = []
    if isinstance(blocks_raw, list):
        for item in blocks_raw:
            block = normalize_block(item)
            if block:
                blocks.append(block)
    heading = _clean_str(raw.get("heading") or raw.get("title"))
    # text 形态的裸字符串小节（模型偶尔直接给字符串列表）
    if not blocks and _clean_str(raw.get("content")):
        blocks = [{"type": "text", "content": _clean_str(raw.get("content"))}]
    if not heading and not blocks:
        return None
    if not heading:
        heading = (blocks[0].get("content") or blocks[0].get("items", ["小节"])[0])[:40]
    stype = _clean_str(raw.get("type")).lower()
    if stype not in SECTION_TYPES:
        stype = "detail"
    return {
        "type": stype,
        "heading": heading,
        "time_stamp": to_hms(raw.get("time_stamp")),
        "important": bool(raw.get("important")),
        "blocks": blocks,
    }


def normalize_chapter(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    sections = []
    for item in raw.get("sections") or []:
        section = normalize_section(item)
        if section:
            sections.append(section)
    title = _clean_str(raw.get("title") or raw.get("heading"))
    if not title and not sections:
        return None
    if not title:
        title = "正文"
    return {
        "title": title,
        "time_stamp": to_hms(raw.get("time_stamp")),
        "intro": _clean_str(raw.get("intro")),
        "sections": sections,
        "summary": _clean_str(raw.get("summary")),
        "key_points": _clean_list(raw.get("key_points")),
    }


def normalize_note(raw: Any) -> dict:
    """把模型产物归一成标准 note_json；容忍缺字段与旧形态（只有 sections）。"""
    data = extract_json(raw)
    if isinstance(data, list):
        # 裸小节列表：包成单章节
        data = {"chapters": [{"title": "", "sections": data}]}
    if not isinstance(data, dict):
        raise ValueError("笔记 JSON 形态不合法：期望对象或数组")

    chapters = []
    for item in data.get("chapters") or []:
        chapter = normalize_chapter(item)
        if chapter:
            chapters.append(chapter)
    if not chapters:
        # map/merge 产物只有 sections：包成单章节
        sections = []
        for item in data.get("sections") or []:
            section = normalize_section(item)
            if section:
                sections.append(section)
        if sections:
            chapters = [{"title": _clean_str(data.get("title")) or "正文",
                         "time_stamp": sections[0]["time_stamp"],
                         "intro": "", "sections": sections,
                         "summary": "", "key_points": []}]
    if not chapters:
        raise ValueError("笔记 JSON 中没有可用的章节/小节内容")

    return {
        "title": _clean_str(data.get("title")) or "视频笔记",
        "summary": _clean_str(data.get("summary")),
        "chapters": chapters,
        "key_takeaways": _clean_list(data.get("key_takeaways")),
        "tags": _clean_list(data.get("tags")),
    }


# ---------------------------------------------------------------- Markdown 派生

def _escape_table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def block_to_markdown(block: dict, *, screenshot: bool = True) -> str:
    btype = block.get("type")
    if btype in ("text", "formula", "quote"):
        content = block.get("content", "")
        if btype == "formula":
            return f"$$\n{content}\n$$"
        if btype == "quote":
            return f"> {content}"
        return content
    if btype == "steps":
        items = block.get("items") or []
        return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))
    if btype == "list":
        items = block.get("items") or []
        if block.get("ordered"):
            return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))
        return "\n".join(f"- {item}" for item in items)
    if btype == "code":
        language = block.get("language") or "text"
        return f"```{language}\n{block.get('content', '')}\n```"
    if btype == "table":
        headers = block.get("headers") or []
        rows = block.get("rows") or []
        lines = ["| " + " | ".join(_escape_table_cell(h) for h in headers) + " |",
                 "| " + " | ".join("---" for _ in headers) + " |"]
        for row in rows:
            lines.append("| " + " | ".join(_escape_table_cell(c) for c in row) + " |")
        return "\n".join(lines)
    if btype == "screenshot":
        content = block.get("content", "")
        if not screenshot:
            # 未开启截图：只保留画面说明，不放标记
            return f"*{content}*" if content else ""
        marker = f"*Screenshot-[{to_marker_time(block.get('time_stamp'))}]"
        return f"{marker}\n\n*{content}*" if content else marker
    return ""


def section_to_markdown(section: dict, chapter_no: int, section_no: int, *, link: bool, screenshot: bool = True) -> List[str]:
    marker = f" *Content-[{to_marker_time(section.get('time_stamp'))}]" if link and to_marker_time(section.get("time_stamp")) else ""
    star = "⭐ " if section.get("important") else ""
    lines = [f"### {chapter_no}.{section_no} {star}{section.get('heading', '')}{marker}".rstrip(), ""]
    for block in section.get("blocks") or []:
        rendered = block_to_markdown(block, screenshot=screenshot)
        if rendered:
            lines.append(rendered)
            lines.append("")
    return lines


def note_to_markdown(
    note: dict,
    *,
    link: bool = True,
    screenshot: bool = True,
    toc: bool = False,
    summary: bool = True,
) -> str:
    """note_json → Markdown。时间戳用 `*Content-[mm:ss]` 标记，截图用 `*Screenshot-[mm:ss]`，
    与既有后处理管线（链接替换 / 截图插入）保持同一协议。"""
    lines: List[str] = [f"# {note.get('title') or '视频笔记'}", ""]
    if note.get("summary"):
        lines.append(note["summary"])
        lines.append("")

    chapters = note.get("chapters") or []

    if toc and chapters:
        lines.append("## 目录")
        lines.append("")
        for i, chapter in enumerate(chapters, start=1):
            lines.append(f"- {i}. {chapter.get('title', '')}")
        lines.append("")

    for i, chapter in enumerate(chapters, start=1):
        marker = f" *Content-[{to_marker_time(chapter.get('time_stamp'))}]" if link and to_marker_time(chapter.get("time_stamp")) else ""
        lines.append(f"## {i}. {chapter.get('title', '')}{marker}".rstrip())
        lines.append("")
        if chapter.get("intro"):
            lines.append(chapter["intro"])
            lines.append("")
        for j, section in enumerate(chapter.get("sections") or [], start=1):
            lines.extend(section_to_markdown(section, i, j, link=link, screenshot=screenshot))
        if chapter.get("summary"):
            lines.append(f"> **本章小结**：{chapter['summary']}")
            lines.append("")
        if chapter.get("key_points"):
            lines.append("**本章要点**")
            lines.append("")
            lines.extend(f"- {point}" for point in chapter["key_points"])
            lines.append("")

    if note.get("key_takeaways"):
        lines.append("## 核心要点")
        lines.append("")
        lines.extend(f"- {point}" for point in note["key_takeaways"])
        lines.append("")

    if summary and note.get("summary"):
        lines.append("## AI 总结")
        lines.append("")
        lines.append(note["summary"])
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    # 3 个以上连续空行压成 2 个，避免派生结果出现大片空白
    return re.sub(r"\n{4,}", "\n\n\n", text)
