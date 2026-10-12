"""复习资料生成（P3）。

输入是合集里的多篇结构化笔记（note_json）；详版走「大纲 → 逐章 → 总览」三步，
每章单独一次调用（进度可见），简版一次成型。产出 content 结构供导出层渲染。
"""
import json
from typing import Callable, List, Optional

from app.gpt.review_prompt import (
    review_brief_prompt,
    review_chapter_prompt,
    review_outline_prompt,
    review_wrapup_prompt,
)
from app.services.quiz_generator import normalize_question
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_CHAPTERS = 12


# ---------------------------------------------------------------- 蒸馏（纯函数）

def distill_note(note: dict, task_id: str = "", index: int = 0) -> dict:
    """把一篇 note_json 压成蒸馏摘要：标题 + 章节标题/要点/小节标题，去掉正文细节。"""
    chapters = []
    for ch in note.get("chapters") or []:
        headings = [s.get("heading", "") for s in (ch.get("sections") or []) if s.get("heading")]
        chapters.append({
            "title": ch.get("title", ""),
            "time_stamp": ch.get("time_stamp", ""),
            "summary": ch.get("summary", ""),
            "key_points": ch.get("key_points") or [],
            "section_headings": headings,
        })
    return {
        "index": index,
        "task_id": task_id,
        "title": note.get("title", ""),
        "summary": note.get("summary", ""),
        "key_takeaways": note.get("key_takeaways") or [],
        "chapters": chapters,
    }


def episode_digest(notes: List[dict], task_ids: Optional[List[str]] = None) -> List[dict]:
    task_ids = task_ids or [""] * len(notes)
    return [distill_note(n, task_ids[i] if i < len(task_ids) else "", i)
            for i, n in enumerate(notes)]


def plan_chapters(outline, digest: List[dict], max_chapters: int = MAX_CHAPTERS) -> List[dict]:
    """把模型排的大纲与各篇笔记对应起来（纯函数，方便测试）。

    episode_refs 缺失/越界时兜底为全部笔记，保证每章都有料可写。
    """
    chapters = (outline or {}).get("chapters") if isinstance(outline, dict) else None
    plans: List[dict] = []
    for ch in chapters or []:
        if not isinstance(ch, dict):
            continue
        title = str(ch.get("title") or "").strip()
        if not title:
            continue
        refs = ch.get("episode_refs")
        if not isinstance(refs, list) or not refs:
            refs = [d["index"] for d in digest]
        eps = [d for d in digest if d["index"] in refs]
        if not eps:
            eps = digest
        plans.append({
            "title": title,
            "goal": str(ch.get("goal") or "").strip(),
            "episodes": eps,
        })
    if not plans:
        plans = [{"title": "核心内容", "goal": "", "episodes": digest}]
    if len(plans) > max_chapters:
        keep = plans[:max_chapters - 1]
        merged_rest = {
            "title": "其他要点",
            "goal": "",
            "episodes": [e for p in plans[max_chapters - 1:] for e in p["episodes"]],
        }
        # 去重 episodes（同一 index 只留一份）
        seen, eps = set(), []
        for e in merged_rest["episodes"]:
            if e["index"] not in seen:
                seen.add(e["index"])
                eps.append(e)
        merged_rest["episodes"] = eps
        plans = keep + [merged_rest]
    return plans


def assemble_material(wrapup, chapters: List[dict], title: str) -> dict:
    """三步产物拼成最终复习资料（纯函数）。"""
    wrapup = wrapup if isinstance(wrapup, dict) else {}

    def _list_of_str(value) -> List[str]:
        return [str(v).strip() for v in (value or []) if str(v).strip()]

    def _pair_list(value, key_a: str, key_b: str) -> List[dict]:
        result = []
        for item in value or []:
            if isinstance(item, dict) and (item.get(key_a) or "").strip():
                result.append({key_a: str(item.get(key_a)).strip(), key_b: str(item.get(key_b) or "").strip()})
        return result

    return {
        "title": title,
        "summary": str(wrapup.get("summary") or "").strip(),
        "goals": _list_of_str(wrapup.get("goals")),
        "chapters": [c for c in chapters if isinstance(c, dict)],
        "confusions": _pair_list(wrapup.get("confusions"), "pair", "difference"),
        "glossary": _pair_list(wrapup.get("glossary"), "term", "meaning"),
        "cards": _pair_list(wrapup.get("cards"), "front", "back"),
    }


def _normalize_chapter(raw) -> Optional[dict]:
    if isinstance(raw, dict) and isinstance(raw.get("chapter"), dict):
        raw = raw["chapter"]
    if not isinstance(raw, dict):
        return None
    sections = []
    for sec in raw.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        heading = str(sec.get("heading") or "").strip()
        content = str(sec.get("content") or "").strip()
        if heading or content:
            sections.append({"heading": heading or "小节", "content": content})
    exercises = []
    for q in raw.get("exercises") or []:
        question = normalize_question(q) if isinstance(q, dict) else None
        if question:
            exercises.append(question)
    title = str(raw.get("title") or "").strip()
    if not title and not sections:
        return None
    return {
        "title": title or "章节",
        "intro": str(raw.get("intro") or "").strip(),
        "sections": sections,
        "exercises": exercises,
    }


def _chapters_digest(chapters: List[dict]) -> List[dict]:
    return [{
        "title": c.get("title", ""),
        "sections": [s.get("heading", "") for s in c.get("sections", [])],
    } for c in chapters]


# ---------------------------------------------------------------- 生成流程

def generate_review_material(
    material_id: int,
    title: str,
    notes: List[dict],
    task_ids: List[str],
    gpt,
    detail_mode: str = "full",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> dict:
    """生成复习资料 content（不负责落库，进度通过 progress_cb 回调）。"""
    def report(msg: str):
        if progress_cb:
            progress_cb(msg)

    if not notes:
        raise ValueError("合集里没有结构化笔记（旧笔记不支持生成复习资料）")

    digest = episode_digest(notes, task_ids)

    if detail_mode == "brief":
        report("简版生成中（一次成型）…")
        data = gpt.chat_json(review_brief_prompt(title, json.dumps(digest, ensure_ascii=False)),
                             purpose="复习资料")
        if isinstance(data, dict) and isinstance(data.get("chapters"), list):
            chapters = [c for c in (_normalize_chapter(ch) for ch in data["chapters"]) if c]
            content = assemble_material(data, chapters, title)
            if chapters:
                content["title"] = str(data.get("title") or title).strip() or title
                return content
        raise ValueError("简版复习资料生成失败：模型未返回可用章节")

    # ---- 详版：大纲 → 逐章 → 总览 ----
    report("① 排大纲…")
    outline = gpt.chat_json(review_outline_prompt(title, json.dumps(digest, ensure_ascii=False)),
                            purpose="复习大纲")
    plans = plan_chapters(outline, digest)
    total = len(plans)

    chapters: List[dict] = []
    for i, plan in enumerate(plans, start=1):
        report(f"② 逐章生成 {i}/{total}：{plan['title']}")
        data = gpt.chat_json(
            review_chapter_prompt(
                title,
                {"title": plan["title"], "goal": plan["goal"]},
                json.dumps(plan["episodes"], ensure_ascii=False),
                i, total,
            ),
            purpose=f"第{i}章",
        )
        chapter = _normalize_chapter(data)
        if chapter:
            if plan["title"] and (not chapter.get("title") or chapter.get("title") == "章节"):
                chapter["title"] = plan["title"]
            chapters.append(chapter)

    if not chapters:
        raise ValueError("逐章生成失败：模型未返回任何章节")

    report("③ 补全学习目标/易混辨析/术语索引/速记卡…")
    wrapup = gpt.chat_json(review_wrapup_prompt(title, json.dumps(_chapters_digest(chapters), ensure_ascii=False)),
                           purpose="复习总览")
    return assemble_material(wrapup, chapters, title)
