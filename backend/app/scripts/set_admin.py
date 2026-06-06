import argparse

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.services.users import get_user_by_email


def main() -> None:
    parser = argparse.ArgumentParser(description="Назначить роль пользователя")
    parser.add_argument("--email", required=True, help="Email пользователя")
    parser.add_argument("--role", default="admin", choices=["user", "admin", "superadmin"], help="Новая роль")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        updated = get_user_by_email(db, args.email)
        if updated is not None:
            updated.role = UserRole(args.role)
            db.commit()
            db.refresh(updated)
    finally:
        db.close()

    if updated is None:
        print("Пользователь не найден")
        raise SystemExit(1)

    print(f"Роль обновлена: {updated.email} -> {updated.role.value}")


if __name__ == "__main__":
    main()
