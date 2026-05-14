import argparse

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.services.users import set_user_admin_role


def main() -> None:
    parser = argparse.ArgumentParser(description="Назначить или снять роль администратора")
    parser.add_argument("--email", required=True, help="Email пользователя")
    parser.add_argument("--is-admin", default="true", choices=["true", "false"], help="true/false")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        updated = set_user_admin_role(db, email=args.email, is_admin=args.is_admin == "true")
    finally:
        db.close()

    if updated is None:
        print("Пользователь не найден")
        raise SystemExit(1)

    role = "admin" if updated.role == UserRole.admin else "user"
    print(f"Роль обновлена: {updated.email} -> {role}")


if __name__ == "__main__":
    main()
