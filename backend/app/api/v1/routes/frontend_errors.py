"""前端错误上报端点：接收前端 sendBeacon POST，写入日志文件。

不做认证（错误可能发生在登录之前），但有基本保护：
  - 单次最多接收 20 条（防刷）
  - 每条消息最长 2000 字符（截断）
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger("app.frontend")


@router.post("/frontend-errors", summary="接收前端错误上报")
async def receive_frontend_errors(request: Request):
    """接收前端 sendBeacon 上报的错误日志，写入文件。

    请求体格式（与 logger.ts 的 entry 一致）：
      [{timestamp, level, tag, message, meta?, error?, requestId?}, ...]
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid_json"}

    entries = body if isinstance(body, list) else [body]

    count = 0
    for entry in entries[:20]:  # 单次最多 20 条
        if not isinstance(entry, dict):
            continue
        msg = entry.get("message", "")
        tag = entry.get("tag", "unknown")
        level = entry.get("level", "error")

        # 截断过长消息
        if isinstance(msg, str) and len(msg) > 2000:
            msg = msg[:2000] + "…"

        extra = {
            "frontend_tag": tag,
            "frontend_level": level,
            "request_id": entry.get("requestId"),
            "url": entry.get("url") or (entry.get("meta", {}).get("url") if isinstance(entry.get("meta"), dict) else None),
            "user_agent": request.headers.get("user-agent", ""),
        }

        # 如果有前端 error 对象，附加 name + stack 首行
        error_obj = entry.get("error")
        if isinstance(error_obj, dict):
            stack = error_obj.get("stack", "")
            first_line = stack.split("\n")[0] if isinstance(stack, str) else ""
            extra["error_name"] = error_obj.get("name", "")
            extra["error_location"] = first_line

        log_method = logger.error if level == "error" else logger.warning
        log_method("🌐 %s", msg, extra=extra)
        count += 1

    return {"status": "ok", "received": count}
