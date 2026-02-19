import os

from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.services.security import hash_password
from app.services.users import create_user, get_user_by_email, get_user_by_username

DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
DEFAULT_ADMIN_DISPLAY_NAME = "Admin"


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def main() -> None:
    email = _env_or_default("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).lower()
    username = _env_or_default("ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME).lower()
    display_name = _env_or_default("ADMIN_DISPLAY_NAME", DEFAULT_ADMIN_DISPLAY_NAME)

    password_raw = os.getenv("ADMIN_PASSWORD")
    password = DEFAULT_ADMIN_PASSWORD if password_raw is None or not password_raw.strip() else password_raw

    db = SessionLocal()
    try:
        existing_by_email = get_user_by_email(db, email)
        existing_by_username = get_user_by_username(db, username)

        existing_users: list[User] = []
        if existing_by_email:
            existing_users.append(existing_by_email)
        if existing_by_username and (
            not existing_users or existing_by_username.id != existing_users[0].id
        ):
            existing_users.append(existing_by_username)

        if existing_users:
            updated = False
            for user in existing_users:
                if user.role != UserRole.admin:
                    user.role = UserRole.admin
                    updated = True
            if updated:
                db.commit()
                print("Updated existing user to admin")
            else:
                print("Admin already exists")
            return

        create_user(
            db=db,
            email=email,
            username=username,
            display_name=display_name,
            hashed_password=hash_password(password),
            role=UserRole.admin,
        )
    except IntegrityError:
        db.rollback()
        print("Admin already exists")
        return
    finally:
        db.close()

    print(f"Created admin: {email} / {username}")


if __name__ == "__main__":
    main()
