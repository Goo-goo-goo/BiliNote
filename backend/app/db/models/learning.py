"""合集/课程数据表：笔记任务按合集聚合，学习状态与进度按合集统计。

（自测题 / 错题本 / 复习资料三块功能已下线，相关表已删除。）
"""
from sqlalchemy import Column, DateTime, Integer, String, func

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
