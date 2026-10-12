"""whisper 模型国内下载源（ModelScope 优先，HF 兜底）。

背景：faster-whisper 默认走 HuggingFace（HF_ENDPOINT 可指 hf-mirror），但 hf-mirror
近年稳定性一般。ModelScope（魔搭）国内直连、无需代理，且托管了同名的
`Systran/faster-whisper-*` 系列（已实测 API 200、文件可下）。

策略（WHISPER_DOWNLOAD_SOURCE 环境变量，默认 modelscope）：
  modelscope → 先 ModelScope 下载到本地镜像目录；失败自动回退 HF 链（HF_ENDPOINT 决定 hf-mirror/官方）
  hf-mirror  → 跳过 ModelScope，强制 HF_ENDPOINT=https://hf-mirror.com
  official   → 跳过 ModelScope，强制 HF_ENDPOINT=https://huggingface.co

布局：ModelScope 下载到 {model_dir}/modelscope/{org}--{name}/ 平铺目录，
加载时把该路径直接交给 WhisperModel（1.1.1 起 os.path.isdir 分支支持本地目录，
不经 download_model，避免 HF cache 布局不匹配的历史坑）。
"""
import os
import shutil
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import requests

from app.utils.logger import get_logger

logger = get_logger(__name__)

MODELSCOPE_API = "https://modelscope.cn/api/v1/models"

# CT2 模型必需文件（缺一不可加载）
REQUIRED_FILES = ("model.bin", "config.json", "tokenizer.json")

ProgressCallback = Optional[Callable[[str, int, int], None]]  # (已下字节, 总字节, 文件序号)


def get_download_source() -> str:
    source = (os.getenv("WHISPER_DOWNLOAD_SOURCE") or "modelscope").strip().lower()
    return source if source in ("modelscope", "hf-mirror", "official") else "modelscope"


def hf_endpoint_override() -> Optional[str]:
    """按下载源返回需要强制的 HF_ENDPOINT（None = 尊重现有环境变量）。"""
    source = get_download_source()
    if source == "hf-mirror":
        return "https://hf-mirror.com"
    if source == "official":
        return "https://huggingface.co"
    return None


def mirror_dir(model_dir: str, repo_id: str) -> Path:
    """ModelScope 本地镜像目录：Org/Name → {root}/modelscope/Org--Name。"""
    return Path(model_dir) / "modelscope" / repo_id.replace("/", "--")


def mirror_complete(path: Path) -> bool:
    """校验镜像目录是否完整可用（必需文件齐全且 model.bin 非空）。"""
    if not path.is_dir():
        return False
    for name in REQUIRED_FILES:
        f = path / name
        if not f.is_file():
            return False
    return (path / "model.bin").stat().st_size > 0


def _list_modelscope_files(repo_id: str) -> List[dict]:
    url = f"{MODELSCOPE_API}/{repo_id}/repo/files"
    resp = requests.get(url, params={"Revision": "master"}, timeout=30)
    resp.raise_for_status()
    data = resp.json() or {}
    files = (data.get("Data") or {}).get("Files") or []
    return [{"path": f.get("Path"), "size": int(f.get("Size") or 0)} for f in files if f.get("Path")]


def _download_modelscope_file(repo_id: str, file_path: str, dest: Path,
                              progress_cb: ProgressCallback, file_no: int, total_files: int) -> None:
    url = f"{MODELSCOPE_API}/{repo_id}/repo"
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, params={"Revision": "master", "FilePath": file_path},
                      stream=True, timeout=(30, 300)) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length") or 0)
        written = 0
        with tmp.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if progress_cb:
                    try:
                        progress_cb(written, total, file_no)
                    except Exception:
                        pass
    tmp.replace(dest)


def download_from_modelscope(repo_id: str, dest: Path, progress_cb: ProgressCallback = None) -> bool:
    """从 ModelScope 下载完整模型到 dest；成功 True，失败自动清理返回 False。"""
    try:
        files = _list_modelscope_files(repo_id)
    except Exception as exc:
        logger.warning(f"[modelscope] 获取 {repo_id} 文件列表失败：{exc}")
        return False

    wanted = {name for name in REQUIRED_FILES}
    # vocabulary.txt 等附属文件一并下（tokenizer 词表，缺了部分模型会报警告）
    extras = {f["path"] for f in files if f["path"] in ("vocabulary.txt", "preprocessor_config.json")}
    targets = [f for f in files if f["path"] in (wanted | extras)]
    if not {f["path"] for f in targets} >= wanted:
        logger.warning(f"[modelscope] {repo_id} 文件不齐（缺必需文件），放弃该源")
        return False

    dest.mkdir(parents=True, exist_ok=True)
    try:
        for idx, item in enumerate(targets, start=1):
            name = item["path"]
            target = dest / name
            if target.exists() and target.stat().st_size == item["size"]:
                continue  # 断点续下：已完整的跳过
            logger.info(f"[modelscope] 下载 {repo_id}/{name}（{round(item['size'] / 1048576, 1)}MB）")
            _download_modelscope_file(repo_id, name, target, progress_cb, idx, len(targets))
        if not mirror_complete(dest):
            raise RuntimeError("下载后校验不通过（必需文件缺失）")
        logger.info(f"[modelscope] {repo_id} 下载完成 → {dest}")
        return True
    except Exception as exc:
        logger.warning(f"[modelscope] 下载 {repo_id} 失败：{exc}，清理半成品")
        shutil.rmtree(dest, ignore_errors=True)
        return False


def ensure_model_local(repo_id: str, model_dir: str, progress_cb: ProgressCallback = None) -> Optional[Path]:
    """确保模型在本地镜像目录就绪；返回可用目录路径，不支持/失败返回 None（交回 HF 链）。

    - 已有完整镜像 → 直接返回（不重复下载）
    - 下载源不是 modelscope → 返回 None
    """
    dest = mirror_dir(model_dir, repo_id)
    if mirror_complete(dest):
        return dest
    if get_download_source() != "modelscope":
        return None
    if download_from_modelscope(repo_id, dest, progress_cb=progress_cb):
        return dest
    return None


def resolve_download_plan() -> Tuple[bool, Optional[str]]:
    """返回 (是否走 ModelScope, HF_ENDPOINT 覆盖值)。"""
    source = get_download_source()
    return source == "modelscope", hf_endpoint_override()
