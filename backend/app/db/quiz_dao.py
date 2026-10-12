"""自测题 + 错题本 DAO。返回纯 dict。"""
import json
from typing import Optional

from app.db.engine import get_db
from app.db.models.learning import QuizQuestion, WrongAnswer
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _question_dict(row: QuizQuestion) -> dict:
    options = []
    if row.options:
        try:
            parsed = json.loads(row.options)
            if isinstance(parsed, list):
                options = [str(o) for o in parsed]
        except Exception:
            options = []
    return {
        "id": row.id,
        "task_id": row.task_id,
        "collection_id": row.collection_id,
        "qtype": row.qtype,
        "difficulty": row.difficulty or "basic",
        "stem": row.stem,
        "options": options,
        "answer": row.answer or "",
        "explanation": row.explanation or "",
        "knowledge_point": row.knowledge_point or "",
        "time_stamp": row.time_stamp or "",
        "created_at": str(row.created_at or ""),
    }


def _wrong_dict(row: WrongAnswer) -> dict:
    return {
        "id": row.id,
        "question_id": row.question_id,
        "task_id": row.task_id or "",
        "qtype": row.qtype or "",
        "question": row.question or "",
        "user_answer": row.user_answer or "",
        "correct_answer": row.correct_answer or "",
        "explanation": row.explanation or "",
        "feedback": row.feedback or "",
        "knowledge_point": row.knowledge_point or "",
        "time_stamp": row.time_stamp or "",
        "status": row.status or "active",
        "wrong_count": row.wrong_count or 1,
        "created_at": str(row.created_at or ""),
        "updated_at": str(row.updated_at or ""),
    }


# ---------------------------------------------------------------- 题目

def save_questions(task_id: str, questions: list, collection_id: Optional[int] = None) -> list:
    """保存一批自测题；同一 task_id 重新生成会清掉旧题。"""
    db = next(get_db())
    try:
        db.query(QuizQuestion).filter_by(task_id=task_id).delete()
        rows = []
        for q in questions:
            row = QuizQuestion(
                task_id=task_id,
                collection_id=collection_id,
                qtype=q.get("qtype", "single"),
                difficulty=q.get("difficulty", "basic"),
                stem=q.get("stem", ""),
                options=json.dumps(q.get("options") or [], ensure_ascii=False),
                answer=q.get("answer", ""),
                explanation=q.get("explanation", ""),
                knowledge_point=q.get("knowledge_point", ""),
                time_stamp=q.get("time_stamp", ""),
            )
            db.add(row)
            rows.append(row)
        db.commit()
        return [_question_dict(r) for r in rows]
    finally:
        db.close()


def save_one_question(task_id: str, question: dict, collection_id: Optional[int] = None) -> Optional[dict]:
    """追加单题（变式题用）。"""
    db = next(get_db())
    try:
        row = QuizQuestion(
            task_id=task_id,
            collection_id=collection_id,
            qtype=question.get("qtype", "single"),
            difficulty=question.get("difficulty", "basic"),
            stem=question.get("stem", ""),
            options=json.dumps(question.get("options") or [], ensure_ascii=False),
            answer=question.get("answer", ""),
            explanation=question.get("explanation", ""),
            knowledge_point=question.get("knowledge_point", ""),
            time_stamp=question.get("time_stamp", ""),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _question_dict(row)
    finally:
        db.close()


def list_questions(task_id: str) -> list:
    db = next(get_db())
    try:
        rows = (db.query(QuizQuestion)
                .filter_by(task_id=task_id)
                .order_by(QuizQuestion.id.asc())
                .all())
        return [_question_dict(r) for r in rows]
    finally:
        db.close()


def get_question(question_id: int) -> Optional[dict]:
    db = next(get_db())
    try:
        row = db.query(QuizQuestion).filter_by(id=question_id).first()
        return _question_dict(row) if row else None
    finally:
        db.close()


# ---------------------------------------------------------------- 错题本

def record_wrong(question: dict, user_answer: str, feedback: str = "") -> dict:
    """错题入库；同 (task_id, 题干) 已存在则 wrong_count+1 并刷新最近作答。"""
    db = next(get_db())
    try:
        row = db.query(WrongAnswer).filter_by(
            task_id=question.get("task_id", ""),
            question=question.get("stem", ""),
        ).first()
        if row:
            row.wrong_count = (row.wrong_count or 1) + 1
            row.user_answer = user_answer
            row.feedback = feedback
            row.status = "active"
        else:
            row = WrongAnswer(
                question_id=question.get("id"),
                task_id=question.get("task_id", ""),
                qtype=question.get("qtype", ""),
                question=question.get("stem", ""),
                user_answer=user_answer,
                correct_answer=question.get("answer", ""),
                explanation=question.get("explanation", ""),
                feedback=feedback,
                knowledge_point=question.get("knowledge_point", ""),
                time_stamp=question.get("time_stamp", ""),
                wrong_count=1,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return _wrong_dict(row)
    finally:
        db.close()


def mark_mastered_by_question(question_id: Optional[int] = None, task_id: str = "",
                              question_text: str = "") -> int:
    """答对后消除错题：按题目 id 或 (task_id, 题干) 把 active 错题置为 mastered。"""
    db = next(get_db())
    try:
        q = db.query(WrongAnswer)
        if question_id:
            rows = q.filter_by(question_id=question_id, status="active").all()
        elif question_text:
            rows = q.filter_by(task_id=task_id, question=question_text, status="active").all()
        else:
            return 0
        for row in rows:
            row.status = "mastered"
        db.commit()
        return len(rows)
    finally:
        db.close()


def list_wrong(active_only: bool = True, task_id: Optional[str] = None, limit: int = 300) -> list:
    db = next(get_db())
    try:
        q = db.query(WrongAnswer)
        if active_only:
            q = q.filter_by(status="active")
        if task_id:
            q = q.filter_by(task_id=task_id)
        rows = q.order_by(WrongAnswer.updated_at.desc()).limit(limit).all()
        return [_wrong_dict(r) for r in rows]
    finally:
        db.close()


def mark_mastered(wrong_id: int) -> Optional[dict]:
    db = next(get_db())
    try:
        row = db.query(WrongAnswer).filter_by(id=wrong_id).first()
        if not row:
            return None
        row.status = "mastered"
        db.commit()
        db.refresh(row)
        return _wrong_dict(row)
    finally:
        db.close()


def delete_wrong(wrong_id: int) -> bool:
    db = next(get_db())
    try:
        row = db.query(WrongAnswer).filter_by(id=wrong_id).first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()
