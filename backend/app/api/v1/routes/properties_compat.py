"""旧 /properties 接口兼容 — 返回空数据避免前端报错"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["properties-compat"])


@router.api_route("/properties", methods=["GET", "POST"])
@router.api_route("/properties/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def properties_compat(request: Request, path: str = ""):
    """兼容旧 /properties/** 请求，返回空列表/成功响应避免前端 404"""
    if request.method == "GET":
        return {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 1}
    return JSONResponse({"message": "ok"})
