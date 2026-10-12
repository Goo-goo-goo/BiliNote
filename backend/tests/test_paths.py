"""统一数据目录（path_helper）的单元测试。

直接按文件路径加载真实 app/utils/path_helper.py（仅依赖 python-dotenv），
monkeypatch DATA_DIR 到 tmp_path，验证：
  - 所有 getter 落在数据根下并自动建目录
  - mkdir 幂等
  - 相对 DATA_DIR 按 backend 项目根解析（不按 cwd）
  - get_db_path 拼 sqlite URL 的斜杠形态
  - get_data_dir 语义 == downloads/
"""
import importlib.util
import os
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "utils" / "path_helper.py"


def _load_module():
    # 桩掉 dotenv，避免测试依赖真实 .env 文件
    if "dotenv" not in sys.modules:
        dotenv_mod = types.ModuleType("dotenv")
        dotenv_mod.load_dotenv = lambda *a, **k: None
        sys.modules["dotenv"] = dotenv_mod
    spec = importlib.util.spec_from_file_location("path_helper_under_test", MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ph = _load_module()


class PathHelperTest(unittest.TestCase):
    def test_all_getters_under_data_root_and_idempotent(self):
        with patch.dict(os.environ, {"DATA_DIR": "/tmp/ph-test-root"}):
            root = ph.get_data_root()
            self.assertEqual(root, "/tmp/ph-test-root")
            getters = [
                ph.get_config_dir, ph.get_upload_dir, ph.get_static_dir,
                ph.get_screenshot_dir, ph.get_cover_dir,
                ph.get_note_results_dir, ph.get_vector_db_dir,
                ph.get_download_cache_dir, ph.get_logs_dir,
            ]
            for getter in getters:
                p = getter()
                self.assertTrue(p.startswith(root), f"{getter.__name__}: {p}")
                self.assertTrue(os.path.isdir(p), f"未自动创建: {p}")
                # 幂等：再调一次路径不变、不抛
                self.assertEqual(getter(), p)

    def test_screenshot_cover_under_static(self):
        with patch.dict(os.environ, {"DATA_DIR": "/tmp/ph-test-root"}):
            self.assertEqual(
                os.path.dirname(ph.get_screenshot_dir()), ph.get_static_dir()
            )
            self.assertEqual(os.path.dirname(ph.get_cover_dir()), ph.get_static_dir())

    def test_db_path_and_sqlite_url(self):
        with patch.dict(os.environ, {"DATA_DIR": "/tmp/ph-test-root"}):
            db = ph.get_db_path()
            self.assertEqual(db, "/tmp/ph-test-root/bili_note.db")
            url = f"sqlite:///{pathlib.Path(db).as_posix()}"
            # POSIX 绝对路径 → sqlite:////abs（4 斜杠）
            self.assertTrue(url.startswith("sqlite:////"), url)

    def test_get_data_dir_is_downloads(self):
        with patch.dict(os.environ, {"DATA_DIR": "/tmp/ph-test-root"}):
            self.assertEqual(ph.get_data_dir(), ph.get_download_cache_dir())
            self.assertTrue(ph.get_data_dir().endswith("/downloads"))

    def test_relative_data_dir_resolves_against_project_root(self):
        with patch.dict(os.environ, {"DATA_DIR": "data-x"}):
            expected = os.path.join(str(ph.PROJECT_ROOT), "data-x")
            self.assertEqual(ph.get_data_root(), expected)
            # getter 会 mkdir，测完清掉仓库里的临时目录
            import shutil

            self.addCleanup(lambda: shutil.rmtree(expected, ignore_errors=True))

    def test_get_app_dir_and_model_dir(self):
        with patch.dict(os.environ, {"DATA_DIR": "/tmp/ph-test-root"}):
            self.assertEqual(
                ph.get_app_dir("grid_output"), "/tmp/ph-test-root/grid_output"
            )
            self.assertEqual(ph.get_app_dir(), "/tmp/ph-test-root")
            self.assertEqual(
                ph.get_model_dir("whisper"), "/tmp/ph-test-root/models/whisper"
            )
            self.assertEqual(
                ph.get_model_dir("mlx-whisper"), "/tmp/ph-test-root/models/mlx-whisper"
            )

    def test_getter_follows_env_change_without_reload(self):
        # getter 不缓存：monkeypatch 换 DATA_DIR 后立即生效
        with patch.dict(os.environ, {"DATA_DIR": "/tmp/ph-a"}):
            self.assertEqual(ph.get_data_root(), "/tmp/ph-a")
        with patch.dict(os.environ, {"DATA_DIR": "/tmp/ph-b"}):
            self.assertEqual(ph.get_data_root(), "/tmp/ph-b")

    def test_project_root_is_backend_dir(self):
        self.assertEqual(pathlib.Path(ph.PROJECT_ROOT).name, "backend")


if __name__ == "__main__":
    unittest.main()
