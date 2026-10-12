"""pytest 全局夹具。

把 DATA_DIR 指到临时目录：path_helper 的 getter 每次调用读 env、不缓存，
所以测试内 monkeypatch.setenv("DATA_DIR", ...) 依然即时生效。
没有这层隔离，真实 app 模块 import 期建目录/写日志会落到仓库 backend/ 里。
"""
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="bilinote-pytest-")
