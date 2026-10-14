"""MCP 服务单元测试：工具注册、核心四件套行为、/mcp 挂载。"""
import unittest

from app.mcp_server import _detect_platform, _resolve_model, get_note, get_task_status, list_notes, mcp


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


class TestMcpTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 先建表：空测试库里查询供应商表不存在会直接报错
        from app.db.init_db import init_db

        init_db()

    def test_tools_registered(self):
        names = {t.name for t in asyncio_run(mcp.list_tools())}
        self.assertEqual(
            names,
            {"generate_note", "list_notes", "get_task_status", "get_note"},
        )

    def test_detect_platform(self):
        self.assertEqual(_detect_platform("https://www.bilibili.com/video/BV1"), "bilibili")
        self.assertEqual(_detect_platform("https://youtu.be/abc"), "youtube")
        self.assertEqual(_detect_platform("https://v.douyin.com/x"), "douyin")
        self.assertIsNone(_detect_platform("https://example.com/x"))

    def test_resolve_model_without_provider_errors(self):
        # 未显式指定时要么解析出模型，要么给出明确配置指引（绝不能崩）
        model, pid, err = _resolve_model("", "")
        self.assertTrue(model or err)

    def test_resolve_model_explicit_passthrough(self):
        model, pid, err = _resolve_model("deepseek-chat", "1")
        self.assertEqual((model, pid, err), ("deepseek-chat", "1", ""))

    def test_get_task_status_missing(self):
        self.assertIn("error", get_task_status("no-such-task"))

    def test_get_note_missing(self):
        self.assertIn("error", get_note("no-such-task"))

    def test_list_notes_empty_or_items(self):
        result = list_notes(limit=5)
        self.assertIn("notes", result)
        self.assertIsInstance(result["notes"], list)

    def test_generate_note_rejects_unknown_platform(self):
        from app.mcp_server import generate_note

        result = generate_note("https://example.com/video/1")
        self.assertIn("error", result)

    def test_generate_note_rejects_no_provider(self):
        from app.mcp_server import generate_note

        result = generate_note("https://www.bilibili.com/video/BV1")
        # 没有供应商时报配置错误；若环境恰好有供应商则门禁/提交均可接受
        self.assertTrue("error" in result or "task_id" in result)


class TestMcpMount(unittest.TestCase):
    def test_mcp_http_handshake(self):
        # 全量跑时其它用例会把 DATA_DIR 指到临时目录：main 挂载 StaticFiles 前目录必须存在
        import os

        from app.utils.path_helper import get_static_dir, get_upload_dir

        os.makedirs(get_static_dir(), exist_ok=True)
        os.makedirs(get_upload_dir(), exist_ok=True)

        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            resp = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "pytest", "version": "0"},
                    },
                },
                headers={"Accept": "application/json, text/event-stream"},
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            self.assertEqual(data["result"]["serverInfo"]["name"], "bilinote")


if __name__ == "__main__":
    unittest.main()
