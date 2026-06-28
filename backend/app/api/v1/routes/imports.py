import os

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.import_service import ImportService

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def _validate_upload(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )
    _, ext = os.path.splitext(file.filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )
    return ext


def _map_ext_to_source_type(ext: str) -> str:
    if ext == ".csv":
        return "csv"
    return "excel"


@router.post("/upload")
async def upload_import(
    file: UploadFile,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    ext = _validate_upload(file)
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE // (1024*1024)} MB",
        )

    source_type = _map_ext_to_source_type(ext)
    import_service = ImportService(session)

    import_task = await import_service.create_import_task(
        admin_id=current_user.id,
        source_name=file.filename,
        source_type=source_type,
    )

    import_task = await import_service.parse_and_import(
        import_task=import_task,
        file_content=content,
        landlord_id=current_user.id,
    )

    await AuditService(session).create_log(
        user_id=current_user.id,
        action="data_import",
        resource_type="import",
        resource_id=import_task.id,
        details={
            "source_name": file.filename,
            "source_type": source_type,
            "total": import_task.total_records,
            "success": import_task.success_records,
            "failed": import_task.failed_records,
        },
    )

    return {
        "id": import_task.id,
        "source_name": import_task.source_name,
        "source_type": import_task.source_type.value,
        "status": import_task.status.value,
        "total_records": import_task.total_records,
        "success_records": import_task.success_records,
        "failed_records": import_task.failed_records,
        "created_at": import_task.created_at.isoformat(),
    }


@router.get("/tasks")
async def list_tasks(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
) -> list[dict]:
    tasks = await ImportService(session).list_tasks(
        skip=skip, limit=limit, status=status,
    )
    return [
        {
            "id": t.id,
            "admin_id": t.admin_id,
            "source_name": t.source_name,
            "source_type": t.source_type.value,
            "status": t.status.value,
            "total_records": t.total_records,
            "success_records": t.success_records,
            "failed_records": t.failed_records,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.get("/tasks/{task_id}")
async def get_task_detail(
    task_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
) -> dict:
    task = await ImportService(session).get_import_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import task not found")

    import json

    error_log = task.error_log
    if error_log:
        try:
            error_log = json.loads(error_log)
        except json.JSONDecodeError:
            pass

    return {
        "id": task.id,
        "admin_id": task.admin_id,
        "source_name": task.source_name,
        "source_type": task.source_type.value,
        "status": task.status.value,
        "total_records": task.total_records,
        "success_records": task.success_records,
        "failed_records": task.failed_records,
        "error_log": error_log,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


@router.post("/tasks/{task_id}/retry")
async def retry_failed_records(
    task_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> dict:
    task = await ImportService(session).get_import_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import task not found")

    if task.status.value not in {"completed", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry task with status '{task.status.value}'",
        )

    task = await ImportService(session).retry_failed(
        import_task=task, landlord_id=current_user.id,
    )

    import json

    error_log = task.error_log
    if error_log:
        try:
            error_log = json.loads(error_log)
        except json.JSONDecodeError:
            pass

    return {
        "id": task.id,
        "source_name": task.source_name,
        "status": task.status.value,
        "total_records": task.total_records,
        "success_records": task.success_records,
        "failed_records": task.failed_records,
        "error_log": error_log,
        "updated_at": task.updated_at.isoformat(),
    }
