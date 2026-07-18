"""Prompt template CRUD. Templates live in SQLite and are edited in the UI."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PromptTemplate
from app.schemas import TemplateCreate, TemplateOut, TemplateUpdate

router = APIRouter(prefix="/templates", tags=["templates"])


def _get_template(template_id: int, db: Session) -> PromptTemplate:
    template = db.get(PromptTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)) -> list[PromptTemplate]:
    return list(db.execute(select(PromptTemplate).order_by(PromptTemplate.name)).scalars())


@router.post("", response_model=TemplateOut, status_code=201)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)) -> PromptTemplate:
    if "{transcript}" not in payload.prompt:
        raise HTTPException(status_code=422, detail="Prompt must contain {transcript}")
    exists = db.execute(
        select(PromptTemplate.id).where(PromptTemplate.slug == payload.slug)
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="A template with this slug already exists")
    template = PromptTemplate(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        prompt=payload.prompt,
        is_builtin=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)) -> PromptTemplate:
    return _get_template(template_id, db)


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int, payload: TemplateUpdate, db: Session = Depends(get_db)
) -> PromptTemplate:
    template = _get_template(template_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if "prompt" in changes and "{transcript}" not in changes["prompt"]:
        raise HTTPException(status_code=422, detail="Prompt must contain {transcript}")
    for field, value in changes.items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)) -> Response:
    template = _get_template(template_id, db)
    db.delete(template)
    db.commit()
    return Response(status_code=204)
