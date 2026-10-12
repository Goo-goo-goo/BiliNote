"""学习存档导出/合并导入集成测试（P4，临时 SQLite + 临时 DATA_DIR）。"""
import io
import json
import unittest
import zipfile

from app.db import collection_dao, quiz_dao
from app.db.init_db import init_db
from app.services.archive import export_archive, import_archive
from app.utils.path_helper import get_note_results_dir

from pathlib import Path


class TestArchiveRoundtrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        # 放一份笔记产物，验证文件进包
        note_dir = Path(get_note_results_dir())
        note_dir.mkdir(parents=True, exist_ok=True)
        (note_dir / "task-a.json").write_text(json.dumps({"markdown": "# hi", "note": None}), encoding="utf-8")
        (note_dir / "task-a_markdown.md").write_text("# hi", encoding="utf-8")
        (note_dir / "task-a_audio.json").write_text("{}", encoding="utf-8")  # 缓存不该进包

        cls.collection = collection_dao.create_collection("存档合集")
        collection_dao.add_item(cls.collection["id"], "task-a", video_id="BV1", platform="bilibili")
        quiz_dao.save_questions("task-a", [
            {"qtype": "single", "difficulty": "basic", "stem": "题干", "options": ["a", "b"],
             "answer": "A", "explanation": "", "knowledge_point": "", "time_stamp": ""},
        ], collection_id=cls.collection["id"])
        quiz_dao.record_wrong({"id": None, "task_id": "task-a", "qtype": "single", "stem": "题干",
                               "answer": "A", "explanation": "", "knowledge_point": "", "time_stamp": ""},
                              "B")

    def test_export_zip_contents(self):
        payload, manifest = export_archive()
        self.assertGreater(manifest["tables"]["collections"], 0)
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            names = zf.namelist()
            self.assertIn("manifest.json", names)
            self.assertIn("data/bili_note.db", names)
            self.assertIn("note_results/task-a.json", names)
            self.assertIn("note_results/task-a_markdown.md", names)
            self.assertNotIn("note_results/task-a_audio.json", names)

    def test_import_dedupes_and_restores(self):
        payload, _ = export_archive()

        # 全量重复导入：全部跳过
        stats1 = import_archive(payload)
        self.assertEqual(stats1["tables"]["collections"]["imported"], 0)
        self.assertGreater(stats1["tables"]["collections"]["skipped"], 0)
        self.assertEqual(stats1["tables"]["quiz_questions"]["imported"], 0)

        # 删掉一条错题再导入：只补回被删的
        wrongs = quiz_dao.list_wrong(active_only=False, task_id="task-a")
        for w in wrongs:
            quiz_dao.delete_wrong(w["id"])
        stats2 = import_archive(payload)
        self.assertEqual(stats2["tables"]["wrong_answers"]["imported"], 1)

        # 文件只增不覆盖
        stats3 = import_archive(payload)
        self.assertGreaterEqual(stats3["files"]["skipped"], 2)

    def test_import_rejects_bad_archive(self):
        with self.assertRaises(ValueError):
            import_archive(b"not a zip")
        # zip 里没有 db 快照也不合法
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "x")
        with self.assertRaises(ValueError):
            import_archive(buf.getvalue())


if __name__ == "__main__":
    unittest.main()
