"""学习存档接口（P4）：导出 zip / 合并导入。"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, Response, UploadFile

from app.services.archive import export_archive, import_archive
from app.utils.response import ResponseWrapper as R

router = APIRouter(prefix="/archive", tags=["archive"])

MAX_UPLOAD_BYTES = 512 * 1024 * 1024  # 512MB 上限（截图多的存档）


@router.get("/export")
def export():
    payload, manifest = export_archive()
    filename = f"bilinote-archive-{manifest.get('exported_at', '')[:10]}.zip"
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_(file: UploadFile):
    payload = await file.read()
    if not payload:
        return R.error("上传文件为空", code=400)
    if len(payload) > MAX_UPLOAD_BYTES:
        return R.error("存档文件过大", code=400)
    try:
        result = import_archive(payload)
    except ValueError as exc:
        return R.error(str(exc), code=400)
    except Exception as exc:
        return R.error(f"导入失败：{exc}", code=500)
    return R.success(data=result)
