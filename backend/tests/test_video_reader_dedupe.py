import importlib.util
import pathlib
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


def _install_stubs():
    app_mod = types.ModuleType("app")
    utils_pkg = types.ModuleType("app.utils")

    logger_mod = types.ModuleType("app.utils.logger")

    class _Logger:
        @staticmethod
        def info(*_args, **_kwargs):
            return None

        @staticmethod
        def warning(*_args, **_kwargs):
            return None

        @staticmethod
        def error(*_args, **_kwargs):
            return None

    def _get_logger(_name):
        return _Logger()

    logger_mod.get_logger = _get_logger

    ffmpeg_mod = types.ModuleType("ffmpeg")
    # 说明：path_helper stub 用共享工厂装全量 getter，避免残缺 stub 污染
    # 同进程里后续测试的 from app.utils.path_helper import X

    pil_mod = types.ModuleType("PIL")
    pil_image_mod = types.ModuleType("PIL.Image")
    pil_draw_mod = types.ModuleType("PIL.ImageDraw")
    pil_font_mod = types.ModuleType("PIL.ImageFont")

    class _FakeImage:
        pass

    class _FakeImageDraw:
        @staticmethod
        def Draw(*_args, **_kwargs):
            return None

    class _FakeImageFont:
        @staticmethod
        def truetype(*_args, **_kwargs):
            return None

        @staticmethod
        def load_default():
            return None

    pil_image_mod.Image = _FakeImage
    pil_draw_mod.ImageDraw = _FakeImageDraw
    pil_font_mod.ImageFont = _FakeImageFont

    def _get_app_dir(name):
        return name

    ffmpeg_mod.probe = lambda *_args, **_kwargs: {"format": {"duration": "0"}}

    sys.modules.setdefault("app", app_mod)
    sys.modules.setdefault("app.utils", utils_pkg)
    sys.modules["PIL"] = pil_mod
    sys.modules["PIL.Image"] = pil_image_mod
    sys.modules["PIL.ImageDraw"] = pil_draw_mod
    sys.modules["PIL.ImageFont"] = pil_font_mod
    sys.modules["ffmpeg"] = ffmpeg_mod
    sys.modules["app.utils.logger"] = logger_mod
    # 全量 getter 的 path_helper stub，仅覆盖本测试依赖特殊行为的 get_app_dir
    try:
        from tests.path_helper_stub import install_path_helper_stub
    except ImportError:
        from path_helper_stub import install_path_helper_stub
    install_path_helper_stub(get_app_dir=_get_app_dir)


def _load_video_reader_module():
    _install_stubs()
    root = pathlib.Path(__file__).resolve().parents[1]
    module_path = root / "app" / "utils" / "video_reader.py"
    spec = importlib.util.spec_from_file_location("video_reader", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("video_reader module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


video_reader_module = _load_video_reader_module()
VideoReader = video_reader_module.VideoReader


def _make_fake_ffmpeg_runner(colors_by_second):
    def _runner(cmd, check=True):
        output_path = next((arg for arg in cmd if isinstance(arg, str) and arg.endswith(".jpg")), None)
        if output_path is None:
            raise AssertionError("Output path not found in ffmpeg cmd")
        match = re.search(r"frame_(\d{2})_(\d{2})\.jpg$", output_path)
        if match is None:
            raise AssertionError("Unexpected output path")
        sec = int(match.group(1)) * 60 + int(match.group(2))
        payload = colors_by_second[sec]
        with open(output_path, "wb") as f:
            f.write(payload)
        return 0

    return _runner


class TestVideoReaderDeduplicateFrames(unittest.TestCase):
    def test_extract_frames_skips_adjacent_duplicates_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir) / "frames"
            grid_dir = pathlib.Path(tmp_dir) / "grids"
            reader = VideoReader(
                video_path="dummy.mp4",
                frame_interval=1,
                frame_dir=str(frame_dir),
                grid_dir=str(grid_dir),
            )

            fake_colors = {
                0: b"frame-a",
                1: b"frame-a",
                2: b"frame-b",
                3: b"frame-b",
            }

            with patch.object(video_reader_module.ffmpeg, "probe", return_value={"format": {"duration": "4"}}), \
                    patch.object(video_reader_module.subprocess, "run", side_effect=_make_fake_ffmpeg_runner(fake_colors)):
                paths = reader.extract_frames(max_frames=10)

            names = [pathlib.Path(p).name for p in paths]
            self.assertEqual(names, ["frame_00_00.jpg", "frame_00_02.jpg"])


if __name__ == "__main__":
    unittest.main()
