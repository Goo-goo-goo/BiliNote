"""学习存档（P4）：导出 zip / 合并导入。

导出内容：DB 快照（学习相关表）+ 笔记产物（{task_id}.json / .note.json / _markdown.md）
+ 截图与封面。导入是**合并**而非覆盖：
  - providers / models / config 不导入（不覆盖本机 API Key 与设置）；
  - 各表按业务键去重，重复的跳过；文件目标已存在的跳过；
  - 失败整体回滚（DB 事务 + 文件只增不覆盖，天然可重入）。
"""
import io
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.db.engine import SessionLocal, get_db_path
from app.db.models.learning import Collection, CollectionItem
from app.db.models.video_tasks import VideoTask
from app.utils.logger import get_logger
from app.utils.path_helper import get_note_results_dir, get_static_dir

logger = get_logger(__name__)

ARCHIVE_VERSION = 1
MANIFEST_NAME = "manifest.json"
DB_NAME = "bili_note.db"

# 导入白名单：学习数据；providers/models/settings 刻意排除（密钥与本机设置不随档迁移）
# （自测题 / 错题本 / 复习资料已下线，老存档里的这些表会被忽略）
IMPORT_TABLES = ("video_tasks", "collections", "collection_items")

_NOTE_SUFFIXES = (".json", ".md")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- 导出

def _snapshot_db(target: Path) -> Dict[str, int]:
    """用 sqlite3 backup API 拍快照（不阻塞写入），返回各表行数。"""
    src = sqlite3.connect(get_db_path())
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    counts: Dict[str, int] = {}
    conn = sqlite3.connect(str(target))
    try:
        for table in IMPORT_TABLES:
            try:
                counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                counts[table] = 0
    finally:
        conn.close()
    return counts


def export_archive() -> Tuple[bytes, Dict]:
    """导出学习存档 zip（返回 zip 字节与清单）。"""
    note_dir = Path(get_note_results_dir())
    static_dir = Path(get_static_dir())

    buffer = io.BytesIO()
    manifest: Dict = {
        "version": ARCHIVE_VERSION,
        "exported_at": _now_iso(),
        "tables": {},
        "files": 0,
    }

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        with tempfile.TemporaryDirectory() as tmp:
            db_snapshot = Path(tmp) / DB_NAME
            manifest["tables"] = _snapshot_db(db_snapshot)
            zf.write(db_snapshot, f"data/{DB_NAME}")

        # 笔记产物：只要结果 JSON / 派生 Markdown，跳过转写与音频缓存
        if note_dir.is_dir():
            for path in sorted(note_dir.iterdir()):
                if not path.is_file() or path.suffix not in _NOTE_SUFFIXES:
                    continue
                if path.name.endswith(("_audio.json", "_transcript.json")) or \
                        path.name.endswith(".gpt.checkpoint.json"):
                    continue
                zf.write(path, f"note_results/{path.name}")
                manifest["files"] += 1

        # 截图与封面
        for sub in ("screenshots", "cover"):
            folder = static_dir / sub
            if folder.is_dir():
                for path in sorted(folder.rglob("*")):
                    if path.is_file():
                        zf.write(path, f"static/{sub}/{path.relative_to(folder).as_posix()}")
                        manifest["files"] += 1

        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))

    return buffer.getvalue(), manifest


# ---------------------------------------------------------------- 导入

def _read_source_rows(db_file: Path) -> Dict[str, List[sqlite3.Row]]:
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    try:
        rows: Dict[str, List[sqlite3.Row]] = {}
        for table in IMPORT_TABLES:
            try:
                rows[table] = conn.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.Error:
                rows[table] = []
        return rows
    finally:
        conn.close()


def _row_payload(row: sqlite3.Row, skip: Tuple[str, ...] = ("id", "created_at", "updated_at")) -> dict:
    """导入载荷：去掉自增 id 与时间戳（时间戳由 server_default 重新生成，
    避免 SQLite 文本时间比对不一致导致去重失效）。"""
    return {k: row[k] for k in row.keys() if k not in skip}


def import_archive(zip_bytes: bytes) -> Dict:
    """合并导入学习存档；返回各表 {imported, skipped} 统计。"""
    stats: Dict[str, Dict[str, int]] = {t: {"imported": 0, "skipped": 0} for t in IMPORT_TABLES}
    files = {"imported": 0, "skipped": 0}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            zf_all = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except zipfile.BadZipFile as exc:
            raise ValueError("不是合法的 zip 存档") from exc
        with zf_all as zf:
            names = zf.namelist()
            if not any(n.endswith(DB_NAME) for n in names):
                raise ValueError("存档里没有数据库快照，格式不合法")
            zf.extractall(tmp_path)

        manifest_file = tmp_path / MANIFEST_NAME
        manifest = {}
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        version = manifest.get("version", ARCHIVE_VERSION)
        if version != ARCHIVE_VERSION:
            raise ValueError(f"存档版本不兼容：{version}（当前支持 {ARCHIVE_VERSION}）")

        source_rows = _read_source_rows(tmp_path / "data" / DB_NAME)

        session = SessionLocal()
        try:
            collection_id_map: Dict[int, int] = {}

            # 1) video_tasks：task_id 唯一
            for row in source_rows.get("video_tasks", []):
                payload = _row_payload(row)
                exists = session.query(VideoTask).filter_by(task_id=payload.get("task_id")).first()
                if exists:
                    stats["video_tasks"]["skipped"] += 1
                    continue
                session.add(VideoTask(**payload))
                stats["video_tasks"]["imported"] += 1

            # 2) collections：name 去重
            for row in source_rows.get("collections", []):
                payload = _row_payload(row)
                exists = session.query(Collection).filter_by(name=payload.get("name")).first()
                if exists:
                    collection_id_map[row["id"]] = exists.id
                    stats["collections"]["skipped"] += 1
                    continue
                obj = Collection(**payload)
                session.add(obj)
                session.flush()
                collection_id_map[row["id"]] = obj.id
                stats["collections"]["imported"] += 1

            # 3) collection_items：(合集, task_id) 去重
            for row in source_rows.get("collection_items", []):
                payload = _row_payload(row)
                mapped = collection_id_map.get(row["collection_id"], row["collection_id"])
                exists = (session.query(CollectionItem)
                          .filter_by(collection_id=mapped, task_id=payload.get("task_id"))
                          .first())
                if exists:
                    stats["collection_items"]["skipped"] += 1
                    continue
                payload["collection_id"] = mapped
                session.add(CollectionItem(**payload))
                stats["collection_items"]["imported"] += 1

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        # 7) 文件合并：目标已存在的一律跳过（只增不覆盖）
        dest_note = Path(get_note_results_dir())
        dest_static = Path(get_static_dir())
        for path in (tmp_path / "note_results").rglob("*") if (tmp_path / "note_results").is_dir() else []:
            if not path.is_file():
                continue
            target = dest_note / path.name
            if target.exists():
                files["skipped"] += 1
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
                files["imported"] += 1
        for sub in ("screenshots", "cover"):
            src_root = tmp_path / "static" / sub
            if not src_root.is_dir():
                continue
            for path in src_root.rglob("*"):
                if not path.is_file():
                    continue
                target = dest_static / sub / path.relative_to(src_root)
                if target.exists():
                    files["skipped"] += 1
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
                    files["imported"] += 1

    logger.info(f"[archive] 存档导入完成：{stats} files={files}")
    return {"tables": stats, "files": files}
