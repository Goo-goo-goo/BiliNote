import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
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
from app import create_app
from app.services.transcriber_config_manager import TranscriberConfigManager
from events import register_handler
from ffmpeg_helper import ensure_ffmpeg_or_raise

logger = get_logger(__name__)
load_dotenv()

# 读取 .env 中的路径
static_path = os.getenv('STATIC', '/static')
out_dir = os.getenv('OUT_DIR', './static/screenshots')

# 自动创建本地目录（static 和 static/screenshots）
static_dir = "static"
uploads_dir = "uploads"
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动序列拆成 5 步、每步独立日志 + 异常时打明确的 [startup N/5 FAILED] 标记。
    # 目的：用户 docker logs 一眼能看出后端死在哪一步，避免「容器一直重启但看不出原因」。
    try:
        logger.info("[startup 1/5] register_handler() — 注册事件处理器")
        register_handler()

        logger.info("[startup 2/5] init_db() — 初始化 SQLite 数据库")
        init_db()

        logger.info("[startup 3/5] TranscriberConfigManager — 读取转写器配置")
        # 转写器不再在启动时强制初始化，而是在首次生成笔记时按需创建。
        # 如果配置了不可用的类型（如 mlx-whisper 未安装），会在使用时报错而非静默回退。
        _cfg = TranscriberConfigManager().get_config()
        logger.info(
            f"           当前转写器: type={_cfg['transcriber_type']}, "
            f"model_size={_cfg['whisper_model_size']}"
        )

        logger.info("[startup 4/5] seed_default_providers() — 初始化默认 LLM 供应商")
        seed_default_providers()

        # 把已配置的代理 export 到环境变量，让 huggingface_hub（whisper 模型下载）
        # 也能走代理——含转写时的按需下载（issue #417）。
        from app.services.proxy_config_manager import ProxyConfigManager
        _proxy = ProxyConfigManager().apply_to_env()
        if _proxy:
            logger.info(f"           已应用全局代理到环境变量: {_proxy}")

        logger.info("[startup 5/5] 启动完成，等待请求")
    except Exception:
        logger.exception("[startup FAILED] 后端启动期异常，详见堆栈；容器会退出并由 restart 策略决定是否重试")
        raise

    yield

app = create_app(lifespan=lifespan)

# 允许的源：本地 web 端 + Tauri 桌面端 + 浏览器扩展（chrome/edge/firefox）
# 用 regex 是因为 chrome-extension://<id> 的 id 在每次开发版加载时不固定
# Tauri 2 不同平台 webview origin 不一样，必须全列：
#   - macOS:   tauri://localhost  （自定义协议）
#   - Windows: https://tauri.localhost  （Edge WebView2）
#   - Linux:   http://tauri.localhost   （WebKitGTK）
# 漏掉哪个都会导致桌面端 fetch 返回 200 但 browser 因为 CORS 拒绝读响应，
# 表现为前端「连不上后端」但后端日志一片 200 OK。
CORS_ORIGIN_REGEX = (
    r"^chrome-extension://[a-z]+$"
    r"|^moz-extension://.+$"
    r"|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
    r"|^tauri://localhost$"
    r"|^https?://tauri\.localhost$"
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
app.mount(static_path, StaticFiles(directory=static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# 挂载前端构建产物，让后端端口直接提供 Web 页面。
# 前端构建时 baseURL 走相对路径 /api，与 include_router 的 /api 前缀同源，无需 CORS。
# 必须挂在所有 API 路由之后：Starlette 按注册顺序匹配，/api、/static、/uploads
# 先命中，剩下的才落到这里的静态文件。
#
# 两个候选位置（按优先级）：
#   1. backend/static/frontend/  —— Docker 单镜像：dist 直接打进 backend 目录
#   2. ../BillNote_frontend/dist —— 本地开发：pnpm build 的产物
# 放在 static/frontend 子目录而非 static 根目录，是为了避免把 static 整体
# 挂载成 volume（截图持久化）时遮蔽前端文件。
_frontend_candidates = [
    os.path.join(os.path.dirname(__file__), "static", "frontend"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "BillNote_frontend", "dist")),
]
frontend_dist = next((p for p in _frontend_candidates if os.path.isdir(p)), None)


class SPAStaticFiles(StaticFiles):
    """单页应用 fallback：未知路径（如直接刷新 /settings）返回 index.html，
    交给 React Router 处理；真实缺失的静态资源仍返回 404。

    注意：Starlette 的 StaticFiles 对不存在的路径抛的是 starlette 的
    HTTPException（FastAPI 的 HTTPException 是其子类，catch 子类抓不到父类），
    所以这里必须 catch starlette 的，而不是检查状态码。"""

    async def get_response(self, path: str, scope):
        from starlette.exceptions import HTTPException

        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code == 404 and "." not in os.path.basename(path):
                return await super().get_response("index.html", scope)
            raise


if frontend_dist and os.path.isdir(frontend_dist):
    app.mount("/", SPAStaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    logger.warning(f"前端构建产物不存在，跳过静态页面挂载: {_frontend_candidates}")


if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8483))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=False)