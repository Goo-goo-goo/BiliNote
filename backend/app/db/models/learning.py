"""学习闭环数据表（P2）：合集/课程 + 自测题 + 错题本。

- Collection / CollectionItem：合集（课程）组织单元，笔记任务按合集聚合，
  学习状态与进度按合集统计；P3 复习资料按合集生成。
- QuizQuestion：基于笔记生成的自测题（single/judge/fill/calc × basic/medium/advanced）。
- WrongAnswer：错题本；答错去重入库（wrong_count 累加），答对标记 mastered。
"""
from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.engine import Base


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CollectionItem(Base):
    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, nullable=False, index=True)
    task_id = Column(String, nullable=False, index=True)
    video_id = Column(String, default="")
    platform = Column(String, default="")
    sort_order = Column(Integer, default=0)
    # 学习状态：unlearned / learning / completed
    learning_status = Column(String, default="unlearned")
    created_at = Column(DateTime, server_default=func.now())


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False, index=True)
    collection_id = Column(Integer, nullable=True, index=True)
    # 题型：single（单选）/ judge（判断）/ fill（填空）/ calc（计算/简答）
    qtype = Column(String, nullable=False)
    # 难度：basic / medium / advanced
    difficulty = Column(String, default="basic")
    stem = Column(Text, nullable=False)
    options = Column(Text, default="")        # JSON 数组（单选题）
    answer = Column(Text, default="")         # 填空："空1等价 / 空1等价 | 空2"；其余为标准答案
    explanation = Column(Text, default="")
    knowledge_point = Column(String, default="")
    time_stamp = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())


class WrongAnswer(Base):
    __tablename__ = "wrong_answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, nullable=True)
    task_id = Column(String, default="", index=True)
    qtype = Column(String, default="")
    question = Column(Text, default="")
    user_answer = Column(Text, default="")
    correct_answer = Column(Text, default="")
    explanation = Column(Text, default="")
    feedback = Column(Text, default="")
    knowledge_point = Column(String, default="")
    time_stamp = Column(String, default="")
    # active（待攻克）/ mastered（已掌握）
    status = Column(String, default="active")
    wrong_count = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReviewMaterial(Base):
    """合集复习资料（P3）。生成流程：大纲 → 逐章 → 总览，进度写在 progress。"""

    __tablename__ = "review_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, nullable=False, index=True)
    title = Column(String, default="")
    # full（大纲→逐章→总览）/ brief（一次成型）
    detail_mode = Column(String, default="full")
    # pending / processing / done / failed
    status = Column(String, default="pending")
    progress = Column(String, default="")
    content_json = Column(Text, default="")
    error = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
