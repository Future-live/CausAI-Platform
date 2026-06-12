from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.favorite import FavoriteItem
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.favorite import FavoriteCreate, FavoriteRead

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _favorite_read(item: FavoriteItem) -> FavoriteRead:
    return FavoriteRead(
        id=item.id,
        kind=item.kind,
        title=item.title,
        description=item.description,
        dataset_id=item.dataset_id,
        group_name=item.group_name,
        sort_order=item.sort_order,
        payload=item.payload_json,
        snapshot=item.snapshot_json,
        created_at=item.created_at.isoformat() if item.created_at else "",
    )


@router.get("", response_model=list[FavoriteRead])
def list_favorites(
    kind: str | None = Query(default=None, max_length=40),
    dataset_id: str | None = Query(default=None, max_length=36),
    group_name: str | None = Query(default=None, max_length=80),
    keyword: str | None = Query(default=None, max_length=80),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort: str = Query(default="-created_at", pattern="^-?(created_at|title|sort_order)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FavoriteRead]:
    query = select(FavoriteItem).where(FavoriteItem.owner_id == user.id)
    if kind:
        query = query.where(FavoriteItem.kind == kind)
    if dataset_id:
        query = query.where(FavoriteItem.dataset_id == dataset_id)
    if group_name:
        query = query.where(FavoriteItem.group_name == group_name)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.where(FavoriteItem.title.ilike(like) | FavoriteItem.description.ilike(like))
    if created_from:
        query = query.where(FavoriteItem.created_at >= created_from)
    if created_to:
        query = query.where(FavoriteItem.created_at <= created_to)

    sort_field = sort.lstrip("-")
    sort_column = {
        "created_at": FavoriteItem.created_at,
        "title": FavoriteItem.title,
        "sort_order": FavoriteItem.sort_order,
    }[sort_field]
    query = query.order_by(sort_column.desc() if sort.startswith("-") else sort_column.asc())
    items = db.scalars(query).all()
    return [_favorite_read(item) for item in items]


@router.post("", response_model=FavoriteRead, status_code=status.HTTP_201_CREATED)
def create_favorite(
    payload: FavoriteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FavoriteRead:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="收藏标题不能为空")
    item = FavoriteItem(
        owner_id=user.id,
        kind=(payload.kind.strip() or "note")[:40],
        title=title[:160],
        description=payload.description.strip() if payload.description else None,
        dataset_id=payload.dataset_id,
        group_name=payload.group_name.strip() if payload.group_name else None,
        sort_order=payload.sort_order,
        payload_json=payload.payload,
        snapshot_json=payload.snapshot,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _favorite_read(item)


@router.delete("/{favorite_id}", response_model=MessageResponse)
def delete_favorite(
    favorite_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    item = db.get(FavoriteItem, favorite_id)
    if not item or item.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="收藏不存在")
    db.delete(item)
    db.commit()
    return MessageResponse(message="已删除收藏")
