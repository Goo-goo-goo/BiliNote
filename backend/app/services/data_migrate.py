"""旧数据自动迁移（P4）。

structured 重构后所有持久化收敛到 DATA_DIR 单根，旧版本的数据散落在 backend/ 各处。
启动时把旧落点**搬**进统一数据目录（目标已存在的文件一律跳过，绝不覆盖），
并在旧位置留一份说明文件。幂等：重复启动不会二次搬迁。

旧落点 → 新落点（相对 backend/ 项目根 → DATA_DIR）：
  bili_note.db            → bili_note.db
  config/                 → config/
  uploads/                → uploads/
  note_results/           → note_results/
  models/                 → models/
  vector_db/              → vector_db/
  static/screenshots/     → static/screenshots/
  static/cover/           → static/cover/
  data/data/              → downloads/   （旧 get_data_dir 的 data/data 双层怪癖）
"""
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from app.utils.logger import get_logger

logger = get_logger(__name__)

LEGACY_MAP: List[Tuple[str, str, str]] = [
    ("bili_note.db", "bili_note.db", "file"),
    ("config", "config", "dir"),
    ("uploads", "uploads", "dir"),
    ("note_results", "note_results", "dir"),
    ("models", "models", "dir"),
    ("vector_db", "vector_db", "dir"),
    ("static/screenshots", "static/screenshots", "dir"),
    ("static/cover", "static/cover", "dir"),
    ("data/data", "downloads", "dir"),
]

_NOTICE_FILE = "BiliNote-数据已迁移.txt"
_NOTICE_TEXT = (
    "BiliNote 已把本目录下的旧数据迁移到统一数据目录（DATA_DIR）。\n"
    "新数据位置可在 .env 通过 DATA_DIR 配置（Docker 内为 /app/data）。\n"
    "迁移是「移动」而非复制，本目录残留的仅是空壳；确认一切正常后可删除。\n"
)


def _move_file(src: Path, dst: Path, stats: Dict[str, List[str]]) -> None:
    if dst.exists():
        stats["skipped"].append(str(src))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    stats["moved"].append(f"{src} -> {dst}")


def _move_dir(src: Path, dst: Path, stats: Dict[str, List[str]]) -> None:
    for path in sorted(src.rglob("*")):
        if path.is_dir():
            continue
        # 迁移说明本身不是数据，别在下一轮被搬走
        if path.name == _NOTICE_FILE:
            continue
        rel = path.relative_to(src)
        _move_file(path, dst / rel, stats)


def migrate_legacy_data(project_root: Path, data_root: Path) -> Dict[str, List[str]]:
    """把 project_root 下的旧落点搬到 data_root；返回 {"moved"/"skipped"/"missing"}。"""
    stats: Dict[str, List[str]] = {"moved": [], "skipped": [], "missing": []}
    project_root = Path(project_root).resolve()
    data_root = Path(data_root).resolve()
    touched_sources: List[Path] = []

    for src_rel, dst_rel, kind in LEGACY_MAP:
        src = project_root / src_rel
        dst = data_root / dst_rel
        if src.resolve() == dst.resolve():
            continue
        if not src.exists():
            stats["missing"].append(str(src))
            continue

        before = len(stats["moved"])
        if kind == "file":
            _move_file(src, dst, stats)
        else:
            _move_dir(src, dst, stats)
        if len(stats["moved"]) > before:
            touched_sources.append(src if kind == "file" else src)

    # 旧位置留说明（只在确实搬过东西的地方；目录空壳保留说明文件）
    # data/data 是要被清掉的空壳，不往里面写说明。
    for src in touched_sources:
        if src.as_posix().endswith("data/data"):
            continue
        notice_dir = src if src.is_dir() else src.parent
        try:
            notice_dir.mkdir(parents=True, exist_ok=True)
            (notice_dir / _NOTICE_FILE).write_text(_NOTICE_TEXT, encoding="utf-8")
        except Exception as exc:
            logger.warning(f"写迁移说明失败 {notice_dir}: {exc}")

    # 清掉搬空的旧 data/data 空壳（仅当它完全空了）
    legacy_cache = project_root / "data" / "data"
    try:
        if legacy_cache.is_dir() and not any(legacy_cache.iterdir()):
            legacy_cache.rmdir()
    except Exception:
        pass

    if stats["moved"]:
        logger.info(f"[data_migrate] 旧数据迁移完成：搬动 {len(stats['moved'])} 项，"
                    f"跳过 {len(stats['skipped'])} 项（目标已存在，不覆盖）")
    return stats
