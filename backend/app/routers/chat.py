"""Follow-up AI chat, grounded in a Mathom's transcript."""

import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, owns
from app.models import ChatMessage, Mathom, User
from app.schemas import ChatMessageOut, ChatRequest
from app.services import ollama

# Interactive requests must not pile up behind a slow remote Ollama. The
# semaphore is deliberately separate from the background recording worker so
# a chat request neither starves uploads nor creates unlimited Ollama calls.
_chat_slots: threading.BoundedSemaphore | None = None
_chat_slots_limit: int | None = None


def _try_acquire_chat_slot() -> bool:
    global _chat_slots, _chat_slots_limit
    from app.config import get_settings

    limit = get_settings().chat_concurrency
    if _chat_slots is None or _chat_slots_limit != limit:
        _chat_slots = threading.BoundedSemaphore(limit)
        _chat_slots_limit = limit
    return _chat_slots.acquire(blocking=False)


router = APIRouter(prefix="/mathoms/{mathom_id}/chat", tags=["chat"])


def _get_mathom(mathom_id: int, db: Session, user: User | None) -> Mathom:
    mathom = db.get(Mathom, mathom_id)
    if mathom is None or not owns(mathom, user):
        raise HTTPException(status_code=404, detail="Mathom not found")
    return mathom


@router.get("", response_model=list[ChatMessageOut])
def list_messages(
    mathom_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[ChatMessage]:
    return _get_mathom(mathom_id, db, user).chat_messages


@router.post("", response_model=list[ChatMessageOut])
def send_message(
    mathom_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[ChatMessage]:
    mathom = _get_mathom(mathom_id, db, user)
    if not mathom.transcript:
        raise HTTPException(status_code=409, detail="Mathom has no transcript yet")
    if not _try_acquire_chat_slot():
        raise HTTPException(
            status_code=429,
            detail="The local AI is busy with another conversation. Please try again shortly.",
            headers={"Retry-After": "5"},
        )

    try:
        history = [{"role": m.role, "content": m.content} for m in mathom.chat_messages]
        reply = ollama.followup_chat(
            mathom.transcript, history, payload.message, language=mathom.language
        )
    finally:
        # The request may time out or Ollama may be unavailable; always free a
        # slot so a transient upstream error cannot block all future chats.
        assert _chat_slots is not None
        _chat_slots.release()

    db.add(ChatMessage(mathom_id=mathom.id, role="user", content=payload.message))
    db.add(ChatMessage(mathom_id=mathom.id, role="assistant", content=reply))
    db.commit()
    db.refresh(mathom)
    return mathom.chat_messages


@router.delete("", status_code=204)
def clear_chat(
    mathom_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> None:
    mathom = _get_mathom(mathom_id, db, user)
    for message in list(mathom.chat_messages):
        db.delete(message)
    db.commit()
