"""自测题生成与判分（P2）。

判分策略（优先本地，尽量不烧 LLM）：
  - single：选项字母归一（A. / A) / 选项A / 选项文本都能识别），本地判；
  - judge ：关键词归一（正确/对/是/√/true …），本地判；
  - fill  ：答案格式「空1等价 / 空1等价 | 空2」规则化比对，本地判（支持逐空反馈）；
  - calc  ：先尝试归一化精确比对，命中本地判；否则交给 AI 批改讲解。
"""
import json
import re
from typing import List, Optional, Tuple

from app.gpt.quiz_prompt import quiz_judge_prompt, quiz_prompt, variant_prompt
from app.utils.logger import get_logger

logger = get_logger(__name__)

VALID_TYPES = ("single", "judge", "fill", "calc")
VALID_DIFFICULTIES = ("basic", "medium", "advanced")

_TRUE_WORDS = ("正确", "对", "是", "true", "t", "yes", "y", "√", "✓")
_FALSE_WORDS = ("错误", "错", "否", "false", "f", "no", "n", "×", "✗")

_PUNCT_RE = re.compile(r"[\s，。、；：！？“”‘’（）()《》【】\[\]{}$\\`*_~\-—→⇒,.;:!?\"'<>/\\|]+")


# ---------------------------------------------------------------- 归一化

def _canonical(text) -> str:
    """答案文本归一：去空白与常见标点、转小写，便于等价比对。"""
    if text is None:
        return ""
    return _PUNCT_RE.sub("", str(text)).lower()


def normalize_single_answer(answer, options: Optional[List[str]] = None) -> str:
    """单选答案归一为选项字母（A/B/C/D）；识别不了返回空串。"""
    raw = str(answer or "").strip()
    if not raw:
        return ""
    m = re.search(r"[A-Da-d]", raw)
    if m and len(raw.strip()) <= 3:  # "A"、"A."、"a)"
        return m.group(0).upper()
    # 给的是选项文本：按内容匹配
    for idx, opt in enumerate(options or []):
        if _canonical(opt) and _canonical(opt) == _canonical(raw):
            return chr(ord("A") + idx)
    return ""


def normalize_judge_answer(answer) -> str:
    """判断答案归一为「正确」/「错误」；识别不了返回空串。"""
    raw = str(answer or "").strip().lower()
    if not raw:
        return ""
    if raw in _TRUE_WORDS or any(w in raw for w in ("正确", "对的", "是的")):
        return "正确"
    if raw in _FALSE_WORDS or any(w in raw for w in ("错误", "不对", "错的", "不是")):
        return "错误"
    return ""


def normalize_fill_answer(answer) -> str:
    """填空答案归一为「空1 / 空1等价 | 空2」：
    每空内等价答案用「 / 」分隔，空与空之间用「 | 」分隔，全文本走 _canonical。
    """
    if isinstance(answer, (list, tuple)):
        parts = [str(a) for a in answer]
    else:
        parts = re.split(r"\s*\|\s*", str(answer or ""))
    blanks = []
    for part in parts:
        equivalents = [e for e in (_canonical(x) for x in re.split(r"\s*/\s*", part)) if e]
        blanks.append(" / ".join(dict.fromkeys(equivalents)))
    return " | ".join(blanks)


def split_fill_blanks(stem: str) -> int:
    """题干里 ____ 空位数量（1-3）。"""
    return len(re.findall(r"_{3,}", stem or "")) or 1


def judge_fill(canonical_answer: str, user_answer) -> Tuple[bool, List[bool]]:
    """填空判分。user_answer 可为数组（每空一项）或字符串（按 | / 逗号 / 顿号 / 空白拆）。

    返回 (是否全对, 逐空对错)。
    """
    expected = [b.strip() for b in canonical_answer.split("|")] if canonical_answer else []
    if isinstance(user_answer, (list, tuple)):
        given = [str(a) for a in user_answer]
    else:
        given = re.split(r"[|,，、\s]+", str(user_answer or "").strip())

    per_blank: List[bool] = []
    for idx, exp in enumerate(expected):
        if idx >= len(given):
            per_blank.append(False)
            continue
        got = _canonical(given[idx])
        equivalents = [e.strip() for e in exp.split("/") if e.strip()]
        per_blank.append(bool(got) and got in equivalents)
    if not per_blank:
        return False, []
    return all(per_blank), per_blank


def normalize_question(raw: dict) -> Optional[dict]:
    """模型产物 → 标准题目；容忍题型别名与缺字段。"""
    if not isinstance(raw, dict):
        return None
    stem = str(raw.get("stem") or raw.get("question") or "").strip()
    if not stem:
        return None

    raw_type = str(raw.get("type") or raw.get("qtype") or "").strip().lower()
    options = [str(o).strip() for o in (raw.get("options") or []) if str(o).strip()]
    if raw_type in ("judge", "bool", "tf", "truefalse") or (
        not options and re.search(r"(判断|是否|对错|正误)", stem)
    ):
        qtype = "judge"
    elif raw_type in ("fill", "blank", "cloze") or re.search(r"_{3,}", stem):
        qtype = "fill"
    elif raw_type in ("single", "choice", "mcq") and options:
        qtype = "single"
    elif raw_type in ("calc", "short", "essay", "proof", "problem"):
        qtype = "calc"
    elif options:
        qtype = "single"
    else:
        qtype = "calc"

    answer = raw.get("answer", "")
    if qtype == "single":
        answer = normalize_single_answer(answer, options)
    elif qtype == "judge":
        answer = normalize_judge_answer(answer)
    elif qtype == "fill":
        answer = normalize_fill_answer(answer)

    difficulty = str(raw.get("difficulty") or "basic").strip().lower()
    if difficulty not in VALID_DIFFICULTIES:
        difficulty = "basic"

    return {
        "qtype": qtype,
        "difficulty": difficulty,
        "stem": stem,
        "options": options if qtype == "single" else [],
        "answer": answer,
        "explanation": str(raw.get("explanation") or "").strip(),
        "knowledge_point": str(raw.get("knowledge_point") or "").strip(),
        "time_stamp": str(raw.get("time_stamp") or "").strip(),
    }


# ---------------------------------------------------------------- 判分

def _grade_local(question: dict, user_answer) -> Optional[dict]:
    """能本地判的题返回 {"correct","feedback"}，否则返回 None 交给 AI。"""
    qtype = question.get("qtype")
    reference = question.get("answer", "")

    if qtype == "single":
        got = normalize_single_answer(user_answer, question.get("options") or [])
        if not got:
            return None
        correct = bool(reference) and got == reference
        return {
            "correct": correct,
            "feedback": "" if correct else f"答案应为 {reference}",
        }

    if qtype == "judge":
        got = normalize_judge_answer(user_answer)
        if not got:
            return None
        correct = bool(reference) and got == reference
        return {
            "correct": correct,
            "feedback": "" if correct else f"答案应为「{reference}」",
        }

    if qtype == "fill":
        canonical = normalize_fill_answer(reference)
        correct, per_blank = judge_fill(canonical, user_answer)
        if correct:
            return {"correct": True, "feedback": ""}
        wrong_idx = [str(i + 1) for i, ok in enumerate(per_blank) if not ok]
        return {
            "correct": False,
            "feedback": f"第 {'、'.join(wrong_idx) or '?'} 空不正确。参考答案：{reference}",
        }

    # calc：先试归一化精确比对
    if _canonical(user_answer) and _canonical(user_answer) == _canonical(reference):
        return {"correct": True, "feedback": ""}
    return None


def grade_question(question: dict, user_answer, gpt=None) -> dict:
    """判分主入口。返回 {"correct","answer","feedback","graded_by"}。

    graded_by: local / ai / none（AI 不可用且本地判不了时不误判，交回调用方展示参考答案）。
    """
    reference = question.get("answer", "")
    local = _grade_local(question, user_answer)
    if local is not None:
        return {
            "correct": local["correct"],
            "answer": reference,
            "feedback": local["feedback"],
            "graded_by": "local",
        }

    if gpt is not None:
        try:
            data = gpt.chat_json(quiz_judge_prompt(
                stem=question.get("stem", ""),
                qtype=question.get("qtype", ""),
                options=question.get("options") or [],
                reference_answer=reference,
                user_answer=str(user_answer),
                knowledge_point=question.get("knowledge_point", ""),
            ), purpose="批改")
            return {
                "correct": bool(data.get("correct")),
                "answer": reference,
                "feedback": str(data.get("feedback") or ""),
                "graded_by": "ai",
            }
        except Exception as exc:
            logger.warning(f"AI 批改失败：{exc}")

    return {
        "correct": None,
        "answer": reference,
        "feedback": "自动批改不可用，请对照参考答案自评。",
        "graded_by": "none",
    }


# ---------------------------------------------------------------- 生成

def generate_quiz(note: dict, gpt, per_tier: int = 3) -> List[dict]:
    """基于笔记 JSON 生成阶梯自测题（归一化后返回）。"""
    data = gpt.chat_json(quiz_prompt(json.dumps(note, ensure_ascii=False), per_tier=per_tier),
                         purpose="自测题")
    raw_questions = data.get("questions") if isinstance(data, dict) else data
    questions = []
    for raw in raw_questions or []:
        question = normalize_question(raw)
        if question:
            questions.append(question)
    return questions


def generate_variant(note: dict, question: dict, gpt) -> Optional[dict]:
    """基于原题生成变式题（同知识点、换情境/问法/数据）。"""
    payload = {
        "type": question.get("qtype"),
        "difficulty": question.get("difficulty"),
        "stem": question.get("stem"),
        "options": question.get("options") or [],
        "answer": question.get("answer"),
        "knowledge_point": question.get("knowledge_point"),
    }
    data = gpt.chat_json(
        variant_prompt(json.dumps(note, ensure_ascii=False), json.dumps(payload, ensure_ascii=False)),
        purpose="变式题",
    )
    raw = data.get("question") if isinstance(data, dict) else None
    return normalize_question(raw or {})
