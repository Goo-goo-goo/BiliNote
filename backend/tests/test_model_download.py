"""whisper 模型下载源单元测试（不触网：只测源解析/布局/完整性判定）。"""
import os
import unittest
from pathlib import Path
import tempfile

from app.transcriber.model_download import (
    get_download_source,
    hf_endpoint_override,
    mirror_complete,
    mirror_dir,
)


class TestDownloadSource(unittest.TestCase):
    def test_default_is_modelscope(self):
        original = os.environ.pop("WHISPER_DOWNLOAD_SOURCE", None)
        try:
            self.assertEqual(get_download_source(), "modelscope")
            self.assertEqual(hf_endpoint_override(), None)  # HF 链尊重现有 HF_ENDPOINT
        finally:
            if original is not None:
                os.environ["WHISPER_DOWNLOAD_SOURCE"] = original

    def test_hf_mirror_and_official_override_endpoint(self):
        original = os.environ.get("WHISPER_DOWNLOAD_SOURCE")
        try:
            os.environ["WHISPER_DOWNLOAD_SOURCE"] = "hf-mirror"
            self.assertEqual(get_download_source(), "hf-mirror")
            self.assertEqual(hf_endpoint_override(), "https://hf-mirror.com")

            os.environ["WHISPER_DOWNLOAD_SOURCE"] = "official"
            self.assertEqual(hf_endpoint_override(), "https://huggingface.co")
        finally:
            if original is None:
                os.environ.pop("WHISPER_DOWNLOAD_SOURCE", None)
            else:
                os.environ["WHISPER_DOWNLOAD_SOURCE"] = original

    def test_invalid_source_falls_back_to_modelscope(self):
        original = os.environ.get("WHISPER_DOWNLOAD_SOURCE")
        try:
            os.environ["WHISPER_DOWNLOAD_SOURCE"] = "gibberish"
            self.assertEqual(get_download_source(), "modelscope")
        finally:
            if original is None:
                os.environ.pop("WHISPER_DOWNLOAD_SOURCE", None)
            else:
                os.environ["WHISPER_DOWNLOAD_SOURCE"] = original


class TestMirrorLayout(unittest.TestCase):
    def test_mirror_dir_layout(self):
        path = mirror_dir("/data/models/whisper", "Systran/faster-whisper-tiny")
        self.assertEqual(path, Path("/data/models/whisper/modelscope/Systran--faster-whisper-tiny"))

    def test_mirror_complete_requires_all_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "m"
            self.assertFalse(mirror_complete(dest))  # 目录不存在

            dest.mkdir()
            (dest / "model.bin").write_bytes(b"x")
            self.assertFalse(mirror_complete(dest))  # 缺 config/tokenizer

            (dest / "config.json").write_text("{}", encoding="utf-8")
            (dest / "tokenizer.json").write_text("{}", encoding="utf-8")
            self.assertTrue(mirror_complete(dest))  # 三件套齐 + model.bin 非空

            (dest / "model.bin").write_bytes(b"")
            self.assertFalse(mirror_complete(dest))  # model.bin 空文件不算完整


if __name__ == "__main__":
    unittest.main()
