"""临时图片上传 — 房源创建前可先传图，返回 URL 后随表单提交"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models.user import User

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_FILES = 15


@router.post("/temp")
async def upload_temp_images(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """上传临时图片，返回临时 URL 列表。后续提交房源时传入 urls 参数即可绑定。"""
    settings = get_settings()
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"最多上传 {MAX_FILES} 张图片")

    temp_dir = Path(settings.upload_dir).resolve() / "temp" / str(current_user.id)
    temp_dir.mkdir(parents=True, exist_ok=True)

    urls = []
    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}")
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件过大: {file.filename}")

        ext = Path(file.filename or "image.jpg").suffix or ".jpg"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        file_path = temp_dir / safe_name
        content = await file.read()
        file_path.write_bytes(content)
        urls.append(f"/api/v1/uploads/temp/{current_user.id}/{safe_name}")

    return JSONResponse(content={"urls": urls, "count": len(urls)}, status_code=201)


@router.post("/temp/batch")
async def upload_temp_batch_images(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """批量导入时上传楼栋共用图片，返回临时 URL 列表。"""
    settings = get_settings()
    if len(files) > 8:
        raise HTTPException(status_code=400, detail="批量共用图片最多上传 8 张")

    temp_dir = Path(settings.upload_dir).resolve() / "temp" / "batch" / str(current_user.id)
    temp_dir.mkdir(parents=True, exist_ok=True)

    urls = []
    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}")
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件过大: {file.filename}")

        ext = Path(file.filename or "image.jpg").suffix or ".jpg"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        file_path = temp_dir / safe_name
        content = await file.read()
        file_path.write_bytes(content)
        urls.append(f"/api/v1/uploads/temp/batch/{current_user.id}/{safe_name}")

    return JSONResponse(content={"urls": urls, "count": len(urls)}, status_code=201)
