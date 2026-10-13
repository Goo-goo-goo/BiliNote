# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BiliNote is an AI video note generation tool, implemented as a **pure Python API service**. It extracts content from video links (Bilibili, YouTube, Douyin, Kuaishou, local files) and generates structured Markdown notes using LLM models. Entry: FastAPI backend (`backend/`), no bundled frontend.

## Development Commands

### Backend (Python 3.11 + FastAPI)
```bash
cd backend
pip install -r requirements.txt
python main.py                    # Starts on 0.0.0.0:8483
pytest                            # Run tests in backend/tests/
pytest tests/test_request_chunker.py::test_name   # Run a single test
```

### Docker
```bash
docker build -t bilinote .                   # 单镜像一键：前端(nginx:80) + 后端(FastAPI:8483，含 /mcp)
docker run -d -p 8080:80 -p 8483:8483 -v ./data:/app/data bilinote
docker-compose up                            # 仅后端 API 单服务，唯一挂载 ./data:/app/data
docker-compose -f docker-compose.gpu.yml up  # GPU variant
```

## Architecture

**Backend** (`backend/`) — FastAPI app, entry point `main.py`:
- `app/routers/` — API routes: `note.py` (generation), `provider.py`, `model.py`, `config.py`, `chat.py` (RAG Q&A on generated notes), `collection.py` (合集/课程), `quiz.py` (自测题/错题本), `review_material.py` (复习资料), `export.py` (Markdown/HTML 导出), `archive.py` (学习存档导出/合并导入)
- `app/mcp_server.py` — MCP 服务（Streamable HTTP，挂载于 `/mcp`）：`generate_note` / `list_notes` / `get_task_status` / `get_note`，复用 `/api` 同一批服务函数
- `app/services/` — Business logic:
  - `note.py` — `NoteGenerator` orchestrates the full pipeline (download → transcribe → LLM → notes)
  - `task_serial_executor.py` — task thread pool (`ConcurrentTaskExecutor`)；并发度由 `TASK_MAX_WORKERS` 控制，默认 1（一次一个任务）
  - `chat_service.py` + `chat_tools.py` + `vector_store.py` — RAG-based AI Q&A with Function Calling, indexing transcripts and video metadata
  - `cookie_manager.py` — per-platform cookie storage; injected into yt-dlp by downloaders (e.g. Bilibili)
  - `transcriber_config_manager.py` — persisted transcriber settings
- `app/downloaders/` — Platform adapters (bilibili, youtube, douyin, kuaishou, local) with shared `base.py` interface
- `app/transcriber/` — Speech-to-text engines (fast-whisper, groq, bcut, kuaishou, mlx-whisper) with factory in `transcriber_provider.py`. YouTube path prefers existing subtitles and skips audio download when available.
- `app/gpt/` — LLM integration with factory pattern (`gpt_factory.py`), structured note pipeline (`prompt.py`, `prompt_builder.py`, `note_render.py`), and `request_chunker.py` for long transcripts
- `app/db/` — SQLite + SQLAlchemy: DAO pattern (`provider_dao.py`, `model_dao.py`, `video_task_dao.py`), models in `models/`
- `app/utils/` — `response.py` (ResponseWrapper for consistent JSON), `video_helper.py` (screenshots via FFmpeg), `path_helper.py` (统一数据目录派生), `screenshot_marker.py` / `note_helper.py` (标记协议)
- `app/validators/video_url_validator.py` — URL → platform detection
- `app/exceptions/` — `BizException` + handlers wired in `main.py` via `register_exception_handlers`
- `backend/events/` — Blinker signal system for post-processing (e.g., temp file cleanup after transcription); registered in `lifespan` startup
- `backend/ffmpeg_helper.py` — `ensure_ffmpeg_or_raise` is called at startup; respects `FFMPEG_BIN_PATH`

**Core Workflow**: client submits URL via API → task queued → download video → extract audio (FFmpeg) → transcribe (Whisper/Groq/etc) → generate structured note (note_json → 派生 Markdown) → client polls `/api/task_status/{task_id}` for completion.

## Key Configuration

- **Ports**: Backend 8483, Docker maps `APP_PORT`→8483
- **Environment**: Root `.env` (copy from `.env.example`). LLM API keys are configured through the provider API, not env vars.
- **Data directory**: All persistent data lives under one root (`DATA_DIR`, default `backend/data/`, `/app/data` in Docker) — SQLite DB, `config/`, `uploads/`, `static/screenshots/`, `static/cover/`, `note_results/`, `vector_db/`, `downloads/`, `models/`, `logs/`. Subdirectories auto-create on access via `backend/app/utils/path_helper.py`.
- **Database**: SQLite at `{DATA_DIR}/bili_note.db`, auto-initialized on first run
- **FFmpeg**: Required system dependency for video/audio processing
- **CORS**: 默认全部放行（`CORS_ORIGIN_REGEX` 环境变量可收紧来源，如 `^https://my\.app$`）
- **Root path** `/` returns a plain-text health line; API docs at `/docs`

## Code Style

- **Backend**: Python with type hints. No configured linter. Uses Pydantic models for validation.
