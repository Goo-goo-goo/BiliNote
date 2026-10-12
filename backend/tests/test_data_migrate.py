"""旧数据自动迁移单元测试（P4）。"""
import tempfile
import unittest
from pathlib import Path

from app.services.data_migrate import migrate_legacy_data


class TestMigrateLegacyData(unittest.TestCase):
    def _make_legacy(self, root: Path):
        (root / "config").mkdir(parents=True)
        (root / "config" / "proxy.json").write_text("{}", encoding="utf-8")
        (root / "data" / "data").mkdir(parents=True)
        (root / "data" / "data" / "cache.mp3").write_bytes(b"x")
        (root / "note_results").mkdir(parents=True)
        (root / "note_results" / "t1.json").write_text("{}", encoding="utf-8")
        (root / "static" / "screenshots").mkdir(parents=True)
        (root / "static" / "screenshots" / "s.jpg").write_bytes(b"img")
        (root / "bili_note.db").write_bytes(b"db")

    def test_moves_all_legacy_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "backend"
            data_root = Path(tmp) / "backend" / "data"
            root.mkdir()
            self._make_legacy(root)

            stats = migrate_legacy_data(root, data_root)

            self.assertEqual(len(stats["moved"]), 5)
            self.assertTrue((data_root / "bili_note.db").exists())
            self.assertTrue((data_root / "config" / "proxy.json").exists())
            self.assertTrue((data_root / "downloads" / "cache.mp3").exists())
            self.assertTrue((data_root / "note_results" / "t1.json").exists())
            self.assertTrue((data_root / "static" / "screenshots" / "s.jpg").exists())
            # 旧位置留说明文件
            self.assertTrue((root / "config" / "BiliNote-数据已迁移.txt").exists())
            # 旧 data/data 空壳被清掉
            self.assertFalse((root / "data" / "data").exists())

    def test_idempotent_second_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "backend"
            data_root = root / "data"
            root.mkdir()
            self._make_legacy(root)
            migrate_legacy_data(root, data_root)
            stats2 = migrate_legacy_data(root, data_root)
            self.assertEqual(stats2["moved"], [])

    def test_existing_target_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "backend"
            data_root = root / "data"
            root.mkdir()
            self._make_legacy(root)
            # 目标已存在且内容不同：必须跳过（不覆盖）
            (data_root / "config").mkdir(parents=True)
            (data_root / "config" / "proxy.json").write_text('{"keep": true}', encoding="utf-8")

            stats = migrate_legacy_data(root, data_root)

            self.assertEqual((data_root / "config" / "proxy.json").read_text(encoding="utf-8"),
                             '{"keep": true}')
            self.assertTrue(any("proxy.json" in s for s in stats["skipped"]))
            # 源文件保持原位（没被搬走也没被删）
            self.assertTrue((root / "config" / "proxy.json").exists())


if __name__ == "__main__":
    unittest.main()
