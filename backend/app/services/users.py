from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.author_favorite import AuthorFavorite
from app.models.enums import UserRole
from app.models.enums import FoodSource, FoodStatus
from app.models.profile import Profile
from app.models.recipe import Recipe
from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def get_usernames_by_ids(db: Session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.username).where(User.id.in_(user_ids))).all()
    return {row_id: username for row_id, username in rows}


def get_user_by_email(db: Session, email: str) -> User | None:
    email = email.strip().lower()
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_username(db: Session, username: str) -> User | None:
    username = username.strip().lower()
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def get_user_by_identifier(db: Session, identifier: str) -> User | None:
    identifier = identifier.strip().lower()
    return db.execute(
        select(User).where(or_(User.email == identifier, User.username == identifier))
    ).scalar_one_or_none()


def create_user(
    db: Session,
    email: str,
    username: str,
    display_name: str | None,
    hashed_password: str,
    role: UserRole = UserRole.user,
) -> User:
    user = User(
        email=email.strip().lower(),
        username=username.strip().lower(),
        display_name=(display_name.strip() if display_name else None),
        hashed_password=hashed_password,
        is_active=True,
        role=role,
    )
    db.add(user)

    # Ensure user.id is available before commit so we can create the default profile
    db.flush()

    profile = Profile(
        user_id=user.id,
        name="Мой профиль",
        target_kcal=None,
        target_protein=None,
        target_fat=None,
        target_carbs=None,
        target_fiber=None,
    )
    db.add(profile)

    db.commit()
    db.refresh(user)
    return user


def set_user_admin_role(db: Session, *, email: str, is_admin: bool) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    user.role = UserRole.admin if is_admin else UserRole.user
    db.commit()
    db.refresh(user)
    return user


def has_public_listed_recipes(db: Session, *, author_id: int) -> bool:
    stmt = (
        select(Recipe.id)
        .where(
            Recipe.owner_user_id == author_id,
            Recipe.source == FoodSource.community,
            Recipe.status == FoodStatus.approved,
            Recipe.is_listed.is_(True),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def add_author_favorite(db: Session, *, user_id: int, author_id: int) -> bool:
    existing = db.execute(
        select(AuthorFavorite).where(
            AuthorFavorite.user_id == user_id,
            AuthorFavorite.author_id == author_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    row = AuthorFavorite(user_id=user_id, author_id=author_id)
    db.add(row)
    db.commit()
    return True


def remove_author_favorite(db: Session, *, user_id: int, author_id: int) -> None:
    db.execute(
        AuthorFavorite.__table__.delete().where(
            AuthorFavorite.user_id == user_id,
            AuthorFavorite.author_id == author_id,
        )
    )
    db.commit()


def list_favorite_author_ids(db: Session, *, user_id: int) -> set[int]:
    rows = db.execute(select(AuthorFavorite.author_id).where(AuthorFavorite.user_id == user_id)).scalars().all()
    return set(rows)


def list_favorite_authors_with_public_counts(db: Session, *, user_id: int) -> list[tuple[int, str, int]]:
    public_recipe_join_condition = and_(
        Recipe.owner_user_id == AuthorFavorite.author_id,
        Recipe.source == FoodSource.community,
        Recipe.status == FoodStatus.approved,
        Recipe.is_listed.is_(True),
    )
    rows = db.execute(
        select(
            AuthorFavorite.author_id,
            User.username,
            func.count(Recipe.id).label("public_recipes_count"),
        )
        .join(User, User.id == AuthorFavorite.author_id)
        .outerjoin(Recipe, public_recipe_join_condition)
        .where(AuthorFavorite.user_id == user_id)
        .group_by(AuthorFavorite.author_id, User.username, AuthorFavorite.created_at)
        .order_by(AuthorFavorite.created_at.desc(), AuthorFavorite.author_id.desc())
    ).all()
    return [(author_id, username, int(public_recipes_count or 0)) for author_id, username, public_recipes_count in rows]
