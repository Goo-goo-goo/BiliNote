"""合集 DAO 集成测试（跑临时 SQLite）。

conftest.py 已把 DATA_DIR 指向临时目录，engine 在 import 时即落到临时库。
"""
import unittest

from app.db.init_db import init_db
from app.db import collection_dao


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


if __name__ == "__main__":
    unittest.main()
