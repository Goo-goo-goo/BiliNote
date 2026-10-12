"""合集 + 自测题/错题本 DAO 集成测试（P2，跑临时 SQLite）。

conftest.py 已把 DATA_DIR 指向临时目录，engine 在 import 时即落到临时库。
"""
import unittest

from app.db.init_db import init_db
from app.db import collection_dao, quiz_dao


class TestCollectionDao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_collection_item_lifecycle(self):
        collection = collection_dao.create_collection("测试合集", "描述")
        self.assertEqual(collection["name"], "测试合集")

        item = collection_dao.add_item(collection["id"], "task-1", video_id="BV1", platform="bilibili")
        self.assertEqual(item["learning_status"], "unlearned")
        self.assertEqual(item["sort_order"], 0)

        # 同合集内 task_id 去重
        again = collection_dao.add_item(collection["id"], "task-1")
        self.assertEqual(again["id"], item["id"])

        item2 = collection_dao.add_item(collection["id"], "task-2")
        self.assertEqual(item2["sort_order"], 1)

        updated = collection_dao.update_item_status(item["id"], "completed")
        self.assertEqual(updated["learning_status"], "completed")

        detail = collection_dao.get_collection(collection["id"])
        self.assertEqual(detail["name"], "测试合集")

        listed = collection_dao.list_collections()
        target = next(c for c in listed if c["id"] == collection["id"])
        self.assertEqual(target["item_count"], 2)
        self.assertEqual(target["completed_count"], 1)

        self.assertTrue(collection_dao.remove_item(collection["id"], item2["id"]))
        self.assertEqual(len(collection_dao.list_items(collection["id"])), 1)

        self.assertTrue(collection_dao.delete_collection(collection["id"]))
        self.assertIsNone(collection_dao.get_collection(collection["id"]))
        self.assertEqual(collection_dao.list_items(collection["id"]), [])

    def test_invalid_status_rejected(self):
        collection = collection_dao.create_collection("状态校验")
        item = collection_dao.add_item(collection["id"], "task-x")
        with self.assertRaises(ValueError):
            collection_dao.update_item_status(item["id"], "done")
        collection_dao.delete_collection(collection["id"])


class TestQuizDao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_question_roundtrip(self):
        questions = [
            {"qtype": "single", "difficulty": "basic", "stem": "1+1=?", "options": ["1", "2"],
             "answer": "B", "explanation": "e", "knowledge_point": "加法", "time_stamp": "00:01:00"},
            {"qtype": "fill", "difficulty": "medium", "stem": "____ 是答案", "options": [],
             "answer": "42", "explanation": "", "knowledge_point": "", "time_stamp": ""},
        ]
        saved = quiz_dao.save_questions("task-q", questions, collection_id=1)
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["options"], ["1", "2"])

        listed = quiz_dao.list_questions("task-q")
        self.assertEqual(len(listed), 2)
        self.assertEqual(quiz_dao.get_question(listed[0]["id"])["stem"], "1+1=?")

        # 重新生成会清掉旧题
        again = quiz_dao.save_questions("task-q", questions[:1])
        self.assertEqual(len(again), 1)
        self.assertEqual(len(quiz_dao.list_questions("task-q")), 1)

    def test_wrong_answer_book(self):
        question = {"id": None, "task_id": "task-w", "qtype": "single", "stem": "错题干",
                    "answer": "A", "explanation": "ex", "knowledge_point": "kp", "time_stamp": ""}

        first = quiz_dao.record_wrong(question, "B", feedback="错因")
        self.assertEqual(first["wrong_count"], 1)

        # 去重累计
        second = quiz_dao.record_wrong(question, "C", feedback="错因2")
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(second["wrong_count"], 2)
        self.assertEqual(second["user_answer"], "C")

        active = quiz_dao.list_wrong(active_only=True, task_id="task-w")
        self.assertEqual(len(active), 1)

        # 答对消除错题
        cleared = quiz_dao.mark_mastered_by_question(task_id="task-w", question_text="错题干")
        self.assertEqual(cleared, 1)
        self.assertEqual(quiz_dao.list_wrong(active_only=True, task_id="task-w"), [])
        self.assertEqual(len(quiz_dao.list_wrong(active_only=False, task_id="task-w")), 1)

        # 再次答错回到 active
        third = quiz_dao.record_wrong(question, "B")
        self.assertEqual(third["status"], "active")

        mastered = quiz_dao.mark_mastered(third["id"])
        self.assertEqual(mastered["status"], "mastered")
        self.assertTrue(quiz_dao.delete_wrong(third["id"]))
        self.assertFalse(quiz_dao.delete_wrong(third["id"]))


if __name__ == "__main__":
    unittest.main()
