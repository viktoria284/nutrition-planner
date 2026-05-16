from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import FavoriteAuthorRead, FavoriteAuthorStateRead
from app.services.users import (
    add_author_favorite,
    get_user_by_id,
    has_public_listed_recipes,
    list_favorite_authors_with_public_counts,
    remove_author_favorite,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/{author_id}/favorite-author", response_model=FavoriteAuthorStateRead)
def post_favorite_author(
    author_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if author_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid author_id")
    if author_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Нельзя добавить себя в избранные авторы.")

    author = get_user_by_id(db, author_id)
    if author is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Автор не найден")

    if not has_public_listed_recipes(db, author_id=author_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="У автора пока нет публичных рецептов.",
        )

    add_author_favorite(db, user_id=current_user.id, author_id=author_id)
    return FavoriteAuthorStateRead(author_id=author_id, is_favorite=True)


@router.delete("/{author_id}/favorite-author", response_model=FavoriteAuthorStateRead)
def delete_favorite_author(
    author_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    remove_author_favorite(db, user_id=current_user.id, author_id=author_id)
    return FavoriteAuthorStateRead(author_id=author_id, is_favorite=False)


@router.get("/favorite-authors", response_model=list[FavoriteAuthorRead])
def get_favorite_authors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = list_favorite_authors_with_public_counts(db, user_id=current_user.id)
    return [
        FavoriteAuthorRead(
            id=author_id,
            username=username,
            public_recipes_count=public_recipes_count,
            is_favorite=True,
        )
        for author_id, username, public_recipes_count in rows
    ]
