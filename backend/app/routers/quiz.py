"""自测题与错题本接口（P2）。

出题基于结构化笔记（note_json）；判分优先本地规则（单选/判断/填空），
计算与简答本地命中不了时交 AI 批改；答错入错题本（去重累计），答对自动销错题。
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import quiz_dao
from app.services import quiz_generator
from app.services.gpt_resolver import resolve_gpt
from app.services.note_store import load_note
from app.utils.response import ResponseWrapper as R

router = APIRouter(prefix="/quiz", tags=["quiz"])


class QuizGenerateRequest(BaseModel):
    task_id: str
    model_name: Optional[str] = None
    provider_id: Optional[str] = None
    per_tier: Optional[int] = 3
    collection_id: Optional[int] = None


class GradeRequest(BaseModel):
    question_id: Optional[int] = None
    # 允许不落库直接判（预览/对答案场景）
    question: Optional[dict] = None
    user_answer: str
    model_name: Optional[str] = None
    provider_id: Optional[str] = None


class VariantRequest(BaseModel):
    question_id: int
    model_name: Optional[str] = None
    provider_id: Optional[str] = None


@router.post("/generate")
def generate_quiz(data: QuizGenerateRequest):
    note = load_note(data.task_id)
    if not note:
        return R.error("该任务没有结构化笔记（旧笔记不支持出题，可重新生成后再试）", code=404)
    try:
        gpt = resolve_gpt(data.model_name, data.provider_id)
    except Exception as exc:
        return R.error(f"模型不可用：{exc}", code=400)

    try:
        questions = quiz_generator.generate_quiz(note, gpt, per_tier=max(1, min(int(data.per_tier or 3), 10)))
    except Exception as exc:
        return R.error(f"出题失败：{exc}", code=500)
    if not questions:
        return R.error("模型没有返回可用题目，请重试", code=500)

    saved = quiz_dao.save_questions(data.task_id, questions, collection_id=data.collection_id)
    return R.success(data={"count": len(saved), "questions": saved})


@router.get("/questions/{task_id}")
def list_questions(task_id: str):
    return R.success(data=quiz_dao.list_questions(task_id))


@router.post("/grade")
def grade(data: GradeRequest):
    question = data.question
    if data.question_id:
        question = quiz_dao.get_question(data.question_id)
        if not question:
            return R.error("题目不存在", code=404)
    if not question:
        return R.error("question_id 与 question 至少给一个", code=400)

    gpt = None
    # 只有本地判不了的题型（calc 等）才需要 AI，惰性解析避免白建客户端
    if question.get("qtype") not in ("single", "judge", "fill"):
        try:
            gpt = resolve_gpt(data.model_name, data.provider_id)
        except Exception:
            gpt = None

    result = quiz_generator.grade_question(question, data.user_answer, gpt=gpt)

    # 错题本联动：答错入库（去重累计），答对消除对应错题
    if result["correct"] is False:
        result["wrong_record"] = quiz_dao.record_wrong(
            question, data.user_answer, feedback=result.get("feedback", "")
        )
    elif result["correct"] is True:
        result["cleared_wrong_count"] = quiz_dao.mark_mastered_by_question(
            question_id=question.get("id"),
            task_id=question.get("task_id", ""),
            question_text=question.get("stem", ""),
        )
    return R.success(data=result)


@router.post("/variant")
def variant(data: VariantRequest):
    question = quiz_dao.get_question(data.question_id)
    if not question:
        return R.error("题目不存在", code=404)
    note = load_note(question.get("task_id", ""))
    if not note:
        return R.error("该任务没有结构化笔记，无法生成变式题", code=404)
    try:
        gpt = resolve_gpt(data.model_name, data.provider_id)
        new_question = quiz_generator.generate_variant(note, question, gpt)
    except Exception as exc:
        return R.error(f"变式题生成失败：{exc}", code=500)
    if not new_question:
        return R.error("模型没有返回可用的变式题", code=500)

    saved = quiz_dao.save_one_question(
        question.get("task_id", ""), new_question, collection_id=question.get("collection_id")
    )
    return R.success(data=saved)


@router.get("/wrong")
def list_wrong(active_only: int = 1, task_id: Optional[str] = None):
    return R.success(data=quiz_dao.list_wrong(active_only=bool(active_only), task_id=task_id))


@router.post("/wrong/{wrong_id}/master")
def master_wrong(wrong_id: int):
    row = quiz_dao.mark_mastered(wrong_id)
    if not row:
        return R.error("错题记录不存在", code=404)
    return R.success(data=row)


@router.delete("/wrong/{wrong_id}")
def delete_wrong(wrong_id: int):
    if not quiz_dao.delete_wrong(wrong_id):
        return R.error("错题记录不存在", code=404)
    return R.success(data={"deleted": wrong_id})
