"""任务状态服务单元测试：富状态文档、阶段轨迹、卡死检测、全局列表。"""
import json
import time
import unittest
from pathlib import Path

from app.enmus.task_status_enums import TaskStatus
from app.services import task_status
from app.utils.path_helper import get_note_results_dir


def _status_file(task_id: str) -> Path:
    return Path(get_note_results_dir()) / f"{task_id}.status.json"


class TestTaskStatus(unittest.TestCase):
    def test_update_writes_rich_doc(self):
        task_status.update_status("t-rich", TaskStatus.PARSING, message="解析视频链接与元信息")
        doc = task_status.read_status("t-rich")

        self.assertEqual(doc["status"], "PARSING")
        self.assertEqual(doc["label"], "解析链接")
        self.assertEqual(doc["step"], 1)
        self.assertEqual(doc["total_steps"], 6)
        self.assertEqual(doc["message"], "解析视频链接与元信息")
        self.assertAlmostEqual(doc["progress"], 0.05, places=2)
        self.assertIn("elapsed_seconds", doc)
        self.assertIn("stale_seconds", doc)
        self.assertFalse(doc["finished"])
        self.assertEqual(len(doc["history"]), 1)

    def test_history_records_transitions_with_elapsed(self):
        task_status.update_status("t-hist", TaskStatus.PARSING, message="解析")
        task_status.update_status("t-hist", TaskStatus.DOWNLOADING, message="下载媒体与元信息")
        task_status.update_status("t-hist", TaskStatus.TRANSCRIBING, message="音频转写中")

        doc = task_status.read_status("t-hist")
        self.assertEqual([h["status"] for h in doc["history"]],
                         ["PARSING", "DOWNLOADING", "TRANSCRIBING"])
        self.assertTrue(all("elapsed" in h for h in doc["history"]))

    def test_set_detail_does_not_grow_history(self):
        task_status.update_status("t-detail", TaskStatus.SUMMARIZING, message="正在生成结构化笔记")
        for i in range(1, 4):
            task_status.set_detail("t-detail", f"分段总结 {i}/3", progress=0.55 + 0.1 * i)

        doc = task_status.read_status("t-detail")
        self.assertEqual(doc["detail"], "分段总结 3/3")
        self.assertAlmostEqual(doc["progress"], 0.85, places=2)
        self.assertEqual(len(doc["history"]), 1)  # 子步骤不刷历史

    def test_fail_records_error(self):
        task_status.update_status("t-fail", TaskStatus.TRANSCRIBING, message="音频转写中")
        task_status.update_status("t-fail", TaskStatus.FAILED, message="转写失败：磁盘满", error="转写失败：磁盘满")

        doc = task_status.read_status("t-fail")
        self.assertEqual(doc["status"], "FAILED")
        self.assertEqual(doc["error"], "转写失败：磁盘满")
        self.assertTrue(doc["finished"])

    def test_success_is_finished_full_progress(self):
        task_status.update_status("t-done", TaskStatus.SUCCESS, message="笔记生成完成")
        doc = task_status.read_status("t-done")
        self.assertTrue(doc["finished"])
        self.assertEqual(doc["progress"], 1.0)
        self.assertEqual(doc["step"], 6)

    def test_list_statuses_sorted_desc(self):
        task_status.update_status("t-list-1", TaskStatus.DOWNLOADING, message="下载中")
        time.sleep(0.01)
        task_status.update_status("t-list-2", TaskStatus.SUMMARIZING, message="总结中")

        items = task_status.list_statuses()
        ids = [i["task_id"] for i in items]
        self.assertIn("t-list-1", ids)
        self.assertIn("t-list-2", ids)
        self.assertEqual(ids.index("t-list-2"), 0)  # 最近更新在前
        target = next(i for i in items if i["task_id"] == "t-list-2")
        self.assertEqual(target["status"], "SUMMARIZING")
        self.assertIn("stale_seconds", target)

    def test_backward_compat_old_format(self):
        # 旧版 {"status","message"} 格式的文件照样能读，字段自动补全
        _status_file("t-old").write_text(
            json.dumps({"status": "SUMMARIZING", "message": "总结中"}), encoding="utf-8"
        )
        doc = task_status.read_status("t-old")
        self.assertEqual(doc["status"], "SUMMARIZING")
        self.assertEqual(doc["label"], "总结中")
        self.assertEqual(doc["total_steps"], 6)
        self.assertEqual(doc["history"], [])
        self.assertFalse(doc["finished"])

    def test_read_missing_returns_none(self):
        self.assertIsNone(task_status.read_status("t-never-existed"))

    def test_progress_anchor_mapping(self):
        task_status.update_status("t-anchor", TaskStatus.TRANSCRIBING)
        self.assertAlmostEqual(task_status.read_status("t-anchor")["progress"], 0.5, places=2)
        task_status.update_status("t-anchor", TaskStatus.SAVING)
        self.assertAlmostEqual(task_status.read_status("t-anchor")["progress"], 0.97, places=2)


if __name__ == "__main__":
    unittest.main()
