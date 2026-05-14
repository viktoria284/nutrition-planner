import argparse

import app.db.base  # noqa: F401

from app.db.session import SessionLocal
from app.services.foods import seed_verified_foods


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed verified foods")
    parser.add_argument(
        "--replace-verified",
        action="store_true",
        help="Delete all verified foods before seeding",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        created = seed_verified_foods(db, replace_existing_values=args.replace_verified)
        print(f"Seed completed. Created verified foods: {created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
