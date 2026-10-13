import re


def prepend_source_link(markdown: str | None, source_url: str) -> str | None:
    """
    在笔记开头添加来源链接；若首个非空行已包含来源链接，则更新该行并避免重复。
    """
    if markdown is None:
        return None

    source = (source_url or "").strip()
    if not source:
        return markdown

    header = f"> 来源链接：{source}"
    lines = markdown.splitlines()
    first_non_empty_idx = None
    for idx, line in enumerate(lines):
        if line.strip():
            first_non_empty_idx = idx
            break

    if first_non_empty_idx is not None:
        first_line = lines[first_non_empty_idx].strip()
        if first_line.startswith("> 来源链接：") or first_line.startswith("来源链接："):
            lines[first_non_empty_idx] = header
            return "\n".join(lines)

    if markdown.strip():
        return f"{header}\n\n{markdown}"
    return header


_CONTENT_MARKER_RE = re.compile(r"[ \t]*\*?Content-(?:\[[0-9:]+\]|[0-9]{1,3}:[0-9]{2}(?::[0-9]{2})?)\*?")
_SCREENSHOT_MARKER_RE = re.compile(r"[ \t]*\*?Screenshot-(?:\[[0-9:]+\]|[0-9]{1,3}:[0-9]{2}(?::[0-9]{2})?)\*?")


def strip_unused_markers(markdown: str, *, link: bool, screenshot: bool) -> str:
    """未开启对应能力时清掉模型写下的标记，避免 *Content- / *Screenshot- 以原文泄漏进笔记。"""
    out = markdown or ""
    if not link:
        out = _CONTENT_MARKER_RE.sub("", out)
    if not screenshot:
        out = _SCREENSHOT_MARKER_RE.sub("", out)
    return re.sub(r"[ \t]+$", "", out, flags=re.M)


def replace_content_markers(markdown: str, video_id: str, platform: str = 'bilibili') -> str:
    """
    替换 *Content-04:16*、Content-04:16 或 Content-[04:16] 为超链接，跳转到对应平台视频的时间位置
    """
    # 匹配四种形式：*Content-04:16*、Content-04:16、Content-[04:16]、Content-[01:04:16]（超 1 小时）
    pattern = r"(?:\*?)Content-(?:\[(?:(\d{1,3}):)?(\d{1,3}):(\d{2})\]|(?:(\d{1,3}):)?(\d{1,3}):(\d{2}))"

    safe_video_id = video_id

    def replacer(match):
        hh = match.group(1) or match.group(4)
        mm = match.group(2) or match.group(5)
        ss = match.group(3) or match.group(6)
        total_seconds = (int(hh) if hh else 0) * 3600 + int(mm) * 60 + int(ss)
        label = f"{hh}:{mm}:{ss}" if hh else f"{mm}:{ss}"

        if platform == 'bilibili':
            # 注意：不能在闭包里给 video_id 赋值（会变局部变量导致 UnboundLocalError），
            # 统一用外部的 safe_video_id 拼 URL
            parsed_video_id = safe_video_id.replace("_p", "?p=")
            url = f"https://www.bilibili.com/video/{parsed_video_id}&t={total_seconds}"
        elif platform == 'youtube':
            url = f"https://www.youtube.com/watch?v={safe_video_id}&t={total_seconds}s"
        elif platform == 'douyin':
            url = f"https://www.douyin.com/video/{safe_video_id}"
            return f"[原片 @ {label}]({url})"
        else:
            return f"({label})"

        return f"[原片 @ {label}]({url})"

    return re.sub(pattern, replacer, markdown)

