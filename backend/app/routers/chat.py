"""Follow-up AI chat, grounded in a Mathom's transcript."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ChatMessage, Mathom
from app.schemas import ChatMessageOut, ChatRequest
from app.services import ollama

router = APIRouter(prefix="/mathoms/{mathom_id}/chat", tags=["chat"])


def _get_mathom(mathom_id: int, db: Session) -> Mathom:
    mathom = db.get(Mathom, mathom_id)
    if mathom is None:
        raise HTTPException(status_code=404, detail="Mathom not found")
    return mathom


@router.get("", response_model=list[ChatMessageOut])
def list_messages(mathom_id: int, db: Session = Depends(get_db)) -> list[ChatMessage]:
    return _get_mathom(mathom_id, db).chat_messages


@router.post("", response_model=list[ChatMessageOut])
def send_message(
    mathom_id: int, payload: ChatRequest, db: Session = Depends(get_db)
) -> list[ChatMessage]:
    mathom = _get_mathom(mathom_id, db)
    if not mathom.transcript:
        raise HTTPException(status_code=409, detail="Mathom has no transcript yet")

    history = [{"role": m.role, "content": m.content} for m in mathom.chat_messages]
    reply = ollama.followup_chat(mathom.transcript, history, payload.message)

    db.add(ChatMessage(mathom_id=mathom.id, role="user", content=payload.message))
    db.add(ChatMessage(mathom_id=mathom.id, role="assistant", content=reply))
    db.commit()
    db.refresh(mathom)
    return mathom.chat_messages


@router.delete("", status_code=204)
def clear_chat(mathom_id: int, db: Session = Depends(get_db)) -> None:
    mathom = _get_mathom(mathom_id, db)
    for message in list(mathom.chat_messages):
        db.delete(message)
    db.commit()
