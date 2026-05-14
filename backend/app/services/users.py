from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.profile import Profile
from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


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
