from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])


# ── SMS 验证码 Redis 辅助函数 ──────────────────────────────

import secrets as _secrets
from redis.asyncio import Redis as _Redis


async def _redis() -> _Redis:
    settings = get_settings()
    return _Redis.from_url(settings.redis_url)


async def store_sms_code(phone: str, code: str, ttl: int = 300) -> None:
    """将验证码存储到 Redis，默认 5 分钟过期"""
    r = await _redis()
    try:
        await r.setex(f"sms_code:{phone}", ttl, code)
    finally:
        await r.close()


async def verify_and_consume_sms_code(phone: str, code: str) -> bool:
    """验证并消费验证码，成功返回 True 并删除 Redis 中的码"""
    r = await _redis()
    try:
        stored = await r.get(f"sms_code:{phone}")
        if stored and stored.decode() == code:
            await r.delete(f"sms_code:{phone}")
            return True
        return False
    finally:
        await r.close()


async def check_sms_rate_limit(phone: str, cooldown: int = 60) -> bool:
    """检查短信发送频率，未超频返回 True，超频返回 False"""
    r = await _redis()
    try:
        key = f"sms_rate:{phone}"
        if await r.exists(key):
            return False
        await r.setex(key, cooldown, "1")
        return True
    finally:
        await r.close()


async def store_reset_token(user_id: int, token: str, ttl: int = 1800) -> None:
    """存储密码重置 token，默认 30 分钟过期"""
    r = await _redis()
    try:
        await r.setex(f"pwd_reset:{token}", ttl, str(user_id))
    finally:
        await r.close()


async def consume_reset_token(token: str) -> int | None:
    """消费密码重置 token，返回 user_id 或 None"""
    r = await _redis()
    try:
        raw = await r.get(f"pwd_reset:{token}")
        if raw:
            await r.delete(f"pwd_reset:{token}")
            return int(raw.decode())
        return None
    finally:
        await r.close()
