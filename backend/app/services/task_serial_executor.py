import os
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable


def _default_max_workers() -> int:
    """并发任务数：环境变量 TASK_MAX_WORKERS 可调，默认 1（串行，一次一个任务）。

    笔记生成是重 IO + 重内存（whisper 转写）的活，默认串行避免多任务挤爆资源；
    机器配置好、需要多任务并行时把 TASK_MAX_WORKERS 调大即可。
    """
    try:
        value = int(os.getenv("TASK_MAX_WORKERS", "1"))
    except (TypeError, ValueError):
        return 1
    return max(1, value)


class ConcurrentTaskExecutor:
    """线程池执行任务。并发度由 TASK_MAX_WORKERS 控制（默认 1，即逐个执行）。"""

    def __init__(self, max_workers: int | None = None):
        self._max_workers = max_workers if (max_workers and max_workers > 0) else _default_max_workers()
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        future: Future = self._pool.submit(fn, *args, **kwargs)
        return future.result()

    def shutdown(self, wait: bool = True):
        self._pool.shutdown(wait=wait)


# 保持向后兼容的导出名
SerialTaskExecutor = ConcurrentTaskExecutor
task_serial_executor = ConcurrentTaskExecutor()
