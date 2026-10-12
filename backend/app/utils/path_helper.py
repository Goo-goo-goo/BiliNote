"""统一数据目录派生。

所有持久化数据都放在单一数据根目录（DATA_ROOT）下，Docker 里把这一个目录
挂出来即可（如 -v ./data:/app/data，env DATA_DIR=/app/data）。

DATA_ROOT 解析优先级：
  1. DATA_DIR 环境变量（相对路径按 backend/ 项目根解析，绝不按 cwd——
     PyInstaller/supervisor/pytest 的 cwd 各不相同，按 cwd 解析是过去
     数据散落各处的根源）
  2. 冻结态（PyInstaller）：<exe 所在目录>/data
  3. 开发态：<backend 项目根>/data

各 getter 每次调用都读 env（不缓存，保证测试 monkeypatch 即时生效），
mkdir(parents=True, exist_ok=True) 后返回绝对路径字符串。
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# backend/ 项目根（app/utils/ 的上两级），不依赖 cwd
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_FILENAME = "bili_note.db"


def _resolve_data_root() -> Path:
    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        root = Path(env_dir)
        if not root.is_absolute():
            root = PROJECT_ROOT / root
    elif getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent / "data"
    else:
        root = PROJECT_ROOT / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_data_root() -> str:
    return str(_resolve_data_root())


def _sub(*parts: str) -> str:
    path = _resolve_data_root().joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


# ---- 数据根下的各子目录 ----

def get_db_path() -> str:
    return str(_resolve_data_root() / DB_FILENAME)


def get_config_dir() -> str:
    return _sub("config")


def get_upload_dir() -> str:
    return _sub("uploads")


def get_static_dir() -> str:
    return _sub("static")


def get_screenshot_dir() -> str:
    return _sub("static", "screenshots")


def get_cover_dir() -> str:
    return _sub("static", "cover")


def get_note_results_dir() -> str:
    return _sub("note_results")


def get_vector_db_dir() -> str:
    return _sub("vector_db")


def get_download_cache_dir() -> str:
    return _sub("downloads")


def get_logs_dir() -> str:
    return _sub("logs")


# ---- 旧入口：签名冻结，下游 downloaders/transcriber/测试的 stub 依赖它们 ----

def get_data_dir() -> str:
    """下载缓存目录。历史上返回 <backend>/data/data（双层怪癖），现统一为 {root}/downloads。"""
    return get_download_cache_dir()


def get_app_dir(subdir: str = "") -> str:
    """数据根的直接子目录（视频理解帧 grid_output/output_frames 等）。"""
    return _sub(subdir) if subdir else get_data_root()


def get_model_dir(subdir: str = "whisper") -> str:
    """模型目录。

    - DATA_DIR 显式设置：{root}/models/{subdir}（Docker/外置数据盘）
    - 冻结态未设 DATA_DIR：APPDATA|~/BiliNote/models/{subdir}（桌面端现状）
    - 开发态默认：{root}/models/{subdir}
    """
    if os.getenv("DATA_DIR"):
        return _sub("models", subdir)
    if getattr(sys, "frozen", False):
        base = Path(os.getenv("APPDATA") or Path.home()) / "BiliNote" / "models"
    else:
        base = _resolve_data_root() / "models"
    path = base / subdir
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
