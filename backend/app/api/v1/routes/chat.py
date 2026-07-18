from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.services.chat_service import ChatService

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────

class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionResponse(BaseModel):
    id: int
    session_id: str
    title: str | None
    status: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    metadata_: dict | None = Field(default=None, alias="metadata")
    created_at: str

    model_config = {"from_attributes": True, "populate_by_name": True}


# ── Routes ────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    chat_service = ChatService(session)
    chat_session = await chat_service.create_session(current_user.id, body.title)
    return SessionResponse(
        id=chat_session.id,
        session_id=chat_session.session_id,
        title=chat_session.title,
        status=chat_session.status.value,
        created_at=chat_session.created_at.isoformat(),
        updated_at=chat_session.updated_at.isoformat(),
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[SessionResponse]:
    chat_service = ChatService(session)
    sessions = await chat_service.list_sessions(current_user.id)
    return [
        SessionResponse(
            id=s.id,
            session_id=s.session_id,
            title=s.title,
            status=s.status.value,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    session_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[MessageResponse]:
    chat_service = ChatService(session)
    messages = await chat_service.get_messages(session_id, current_user.id)
    return [
        MessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role.value,
            content=m.content,
            metadata=m.metadata_,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    body: MessageRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    chat_service = ChatService(session)

    # Fetch existing history for this session
    existing_messages = await chat_service.get_messages(session_id, current_user.id)
    history = [
        {"role": m.role.value, "content": m.content}
        for m in existing_messages
    ]

    return StreamingResponse(
        chat_service.chat_stream(session_id, current_user.id, body.content, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    chat_service = ChatService(session)
    deleted = await chat_service.delete_session(session_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
