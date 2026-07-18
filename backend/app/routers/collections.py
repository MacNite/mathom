"""Collections: named shelves of Mathoms."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Collection, Mathom
from app.schemas import CollectionCreate, CollectionOut, CollectionUpdate

router = APIRouter(prefix="/collections", tags=["collections"])


def _get_collection(collection_id: int, db: Session) -> Collection:
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.get("", response_model=list[CollectionOut])
def list_collections(db: Session = Depends(get_db)) -> list[Collection]:
    return list(db.execute(select(Collection).order_by(Collection.name)).scalars())


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(payload: CollectionCreate, db: Session = Depends(get_db)) -> Collection:
    exists = db.execute(select(Collection.id).where(Collection.name == payload.name)).first()
    if exists:
        raise HTTPException(status_code=409, detail="A collection with this name already exists")
    collection = Collection(name=payload.name, description=payload.description)
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


@router.get("/{collection_id}", response_model=CollectionOut)
def get_collection(collection_id: int, db: Session = Depends(get_db)) -> Collection:
    return _get_collection(collection_id, db)


@router.put("/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: int, payload: CollectionUpdate, db: Session = Depends(get_db)
) -> Collection:
    collection = _get_collection(collection_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(collection, field, value)
    db.commit()
    db.refresh(collection)
    return collection


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: int, db: Session = Depends(get_db)) -> Response:
    collection = _get_collection(collection_id, db)
    db.delete(collection)
    db.commit()
    return Response(status_code=204)


@router.post("/{collection_id}/mathoms/{mathom_id}", response_model=CollectionOut)
def add_mathom(collection_id: int, mathom_id: int, db: Session = Depends(get_db)) -> Collection:
    collection = _get_collection(collection_id, db)
    mathom = db.get(Mathom, mathom_id)
    if mathom is None:
        raise HTTPException(status_code=404, detail="Mathom not found")
    if mathom not in collection.mathoms:
        collection.mathoms.append(mathom)
    db.commit()
    db.refresh(collection)
    return collection


@router.delete("/{collection_id}/mathoms/{mathom_id}", response_model=CollectionOut)
def remove_mathom(collection_id: int, mathom_id: int, db: Session = Depends(get_db)) -> Collection:
    collection = _get_collection(collection_id, db)
    collection.mathoms = [m for m in collection.mathoms if m.id != mathom_id]
    db.commit()
    db.refresh(collection)
    return collection
