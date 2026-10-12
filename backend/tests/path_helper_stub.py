"""共享的 app.utils.path_helper 完整 stub 工厂。

部分单测用轻量 stub 加载被测模块（避免拉起 faster-whisper 等重依赖）。
但残缺的 path_helper stub 一旦进入 sys.modules，会污染同进程里后续的测试——
例如只带 get_app_dir 的 stub 会让 whisper_models 的 get_config_dir 导入失败。
这里提供完整 getter 集合，任何收集顺序下 `from app.utils.path_helper import X` 都能成功。
"""
import os
import sys
import tempfile
import types


def make_path_helper_stub(data_root: str | None = None) -> types.ModuleType:
    root = data_root or os.path.join(tempfile.gettempdir(), "bilinote-test-data")

    def _p(*parts: str) -> str:
        return os.path.join(root, *parts)

    mod = types.ModuleType("app.utils.path_helper")
    mod.PROJECT_ROOT = root
    mod.get_data_root = lambda: root
    mod.get_db_path = lambda: _p("bili_note.db")
    mod.get_config_dir = lambda: _p("config")
    mod.get_upload_dir = lambda: _p("uploads")
    mod.get_static_dir = lambda: _p("static")
    mod.get_screenshot_dir = lambda: _p("static", "screenshots")
    mod.get_cover_dir = lambda: _p("static", "cover")
    mod.get_note_results_dir = lambda: _p("note_results")
    mod.get_vector_db_dir = lambda: _p("vector_db")
    mod.get_download_cache_dir = lambda: _p("downloads")
    mod.get_logs_dir = lambda: _p("logs")
    mod.get_data_dir = lambda: _p("downloads")
    mod.get_app_dir = lambda subdir="": _p(subdir) if subdir else root
    mod.get_model_dir = lambda subdir="whisper": _p("models", subdir)
    return mod


def install_path_helper_stub(**attrs) -> types.ModuleType:
    """安装完整 stub（覆盖已有的同名条目），可用 attrs 覆盖个别 getter。"""
    mod = make_path_helper_stub()
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules["app.utils.path_helper"] = mod
    return mod
