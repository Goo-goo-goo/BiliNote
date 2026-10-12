"""任务执行器测试。

契约（与实现 task_serial_executor.py 对齐）：
  - 并发度由环境变量 TASK_MAX_WORKERS 控制，默认 1（一次一个任务）；
  - 显式给 max_workers > 1 时允许并发执行。
"""
import importlib.util
import os
import pathlib
import threading
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "services" / "task_serial_executor.py"
spec = importlib.util.spec_from_file_location("task_serial_executor", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("task_serial_executor module spec not found")
task_serial_executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_serial_executor)
SerialTaskExecutor = task_serial_executor.SerialTaskExecutor
ConcurrentTaskExecutor = task_serial_executor.ConcurrentTaskExecutor


class TestTaskExecutor(unittest.TestCase):
    def test_default_runs_tasks_one_by_one(self):
        """默认（TASK_MAX_WORKERS 未设）就是串行：任何时刻只允许一个任务在跑。"""
        original = os.environ.pop("TASK_MAX_WORKERS", None)
        try:
            executor = ConcurrentTaskExecutor()
        finally:
            if original is not None:
                os.environ["TASK_MAX_WORKERS"] = original

        state_lock = threading.Lock()
        state = {"active": 0, "peak_active": 0}

        def critical_work():
            with state_lock:
                state["active"] += 1
                state["peak_active"] = max(state["peak_active"], state["active"])
            time.sleep(0.05)
            with state_lock:
                state["active"] -= 1

        threads = [threading.Thread(target=lambda: executor.run(critical_work)) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        executor.shutdown()

        self.assertEqual(state["peak_active"], 1)

    def test_max_workers_from_env(self):
        original = os.environ.get("TASK_MAX_WORKERS")
        try:
            os.environ.pop("TASK_MAX_WORKERS", None)
            self.assertEqual(ConcurrentTaskExecutor()._max_workers, 1)

            os.environ["TASK_MAX_WORKERS"] = "3"
            self.assertEqual(ConcurrentTaskExecutor()._max_workers, 3)

            # 非法值与 0 都回落到默认 1
            os.environ["TASK_MAX_WORKERS"] = "abc"
            self.assertEqual(ConcurrentTaskExecutor()._max_workers, 1)
            os.environ["TASK_MAX_WORKERS"] = "0"
            self.assertEqual(ConcurrentTaskExecutor()._max_workers, 1)
        finally:
            if original is None:
                os.environ.pop("TASK_MAX_WORKERS", None)
            else:
                os.environ["TASK_MAX_WORKERS"] = original

    def test_concurrent_when_workers_gt_one(self):
        """显式 max_workers=2 时两个任务必须能同时在跑（用 Barrier 会合验证）。"""
        executor = SerialTaskExecutor(max_workers=2)
        barrier = threading.Barrier(2, timeout=5)
        errors = []

        def work():
            try:
                barrier.wait()  # 只有两个任务真正并发时才能会合
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=lambda: executor.run(work)) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        executor.shutdown()

        self.assertEqual(errors, [])  # 串行执行会让 Barrier 超时破掉
        self.assertFalse(barrier.broken)


if __name__ == "__main__":
    unittest.main()
