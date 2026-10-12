import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.db.init_db import init_db
from app.db.provider_dao import seed_default_providers
from app.exceptions.exception_handlers import register_exception_handlers
# from app.db.model_dao import init_model_table
# from app.db.provider_dao import init_provider_table
from app.utils.logger import get_logger
from app.utils.path_helper import (
    get_data_root,
    get_static_dir,
    get_upload_dir,
    get_screenshot_dir,
    get_cover_dir,
    get_note_results_dir,
    get_vector_db_dir,
    get_download_cache_dir,
    get_logs_dir,
    get_config_dir,
)
from app import create_app
from app.services.data_migrate import migrate_legacy_data
from app.services.transcriber_config_manager import TranscriberConfigManager
from events import register_handler
from ffmpeg_helper import ensure_ffmpeg_or_raise

logger = get_logger(__name__)
load_dotenv()

# URL 挂载前缀（纯 URL，不涉及磁盘路径）
static_path = os.getenv('STATIC', '/static')

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动序列拆成 7 步、每步独立日志 + 异常时打明确的 [startup N/7 FAILED] 标记。
    # 目的：用户 docker logs 一眼能看出后端死在哪一步，避免「容器一直重启但看不出原因」。
    try:
        logger.info("[startup 1/7] 旧数据自动迁移 — 旧落点搬进统一数据目录（不覆盖已存在文件）")
        data_root = Path(get_data_root())
        migrate_stats = migrate_legacy_data(Path(__file__).resolve().parent, data_root)
        if migrate_stats["moved"]:
            logger.info(f"           迁移完成：搬动 {len(migrate_stats['moved'])} 项")

        logger.info("[startup 2/7] 预建统一数据目录 — DATA_DIR 下的子目录幂等创建")
        data_root = get_data_root()
        for ensure in (
            get_config_dir, get_upload_dir, get_static_dir, get_screenshot_dir,
            get_cover_dir, get_note_results_dir, get_vector_db_dir,
            get_download_cache_dir, get_logs_dir,
        ):
            ensure()
        logger.info(f"           数据根目录: {data_root}")

        logger.info("[startup 3/7] register_handler() — 注册事件处理器")
        register_handler()

        logger.info("[startup 4/7] init_db() — 初始化 SQLite 数据库")
        init_db()

        logger.info("[startup 5/7] TranscriberConfigManager — 读取转写器配置")
        # 转写器不再在启动时强制初始化，而是在首次生成笔记时按需创建。
        # 如果配置了不可用的类型（如 mlx-whisper 未安装），会在使用时报错而非静默回退。
        _cfg = TranscriberConfigManager().get_config()
        logger.info(
            f"           当前转写器: type={_cfg['transcriber_type']}, "
            f"model_size={_cfg['whisper_model_size']}"
        )

        logger.info("[startup 6/7] seed_default_providers() — 初始化默认 LLM 供应商")
        seed_default_providers()

        # 把已配置的代理 export 到环境变量，让 huggingface_hub（whisper 模型下载）
        # 也能走代理——含转写时的按需下载（issue #417）。
        from app.services.proxy_config_manager import ProxyConfigManager
        _proxy = ProxyConfigManager().apply_to_env()
        if _proxy:
            logger.info(f"           已应用全局代理到环境变量: {_proxy}")

        logger.info("[startup 7/7] 启动完成，等待请求")
    except Exception:
        logger.exception("[startup FAILED] 后端启动期异常，详见堆栈；容器会退出并由 restart 策略决定是否重试")
        raise

    yield

app = create_app(lifespan=lifespan)

# 允许的源：本地客户端（curl/脚本/本地工具）。
# 项目为纯 Python API 服务；如需给远程前端开 CORS，改这里的正则或自行加中间件。
CORS_ORIGIN_REGEX = (
    r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
register_exception_handlers(app)
app.mount(static_path, StaticFiles(directory=get_static_dir()), name="static")
app.mount("/uploads", StaticFiles(directory=get_upload_dir()), name="uploads")


# 项目已转纯 Python API 服务：不再挂载任何前端构建产物（SPAStaticFiles 已移除）。
# 根路径给一行纯文本健康信息，方便 curl / docker healthcheck 探活。
@app.get("/", include_in_schema=False)
def root():
    return PlainTextResponse("BiliNote API is running. See /docs for API documentation.")


if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8483))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=False)