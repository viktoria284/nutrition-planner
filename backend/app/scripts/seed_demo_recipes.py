import argparse

import app.db.base  # noqa: F401

from app.db.session import SessionLocal
from app.services.recipes import seed_demo_public_recipes


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo public recipes")
    parser.add_argument(
        "--replace-demo",
        action="store_true",
        help="Delete existing demo recipes before seeding",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = seed_demo_public_recipes(db, replace_demo=args.replace_demo)
        print(
            "Seed completed. "
            f"created={stats['created_recipes']}, "
            f"skipped={stats['skipped_recipes']}, "
            f"total={stats['total_demo_recipes']}, "
            f"breakfast={stats['breakfast']}, "
            f"lunch={stats['lunch']}, "
            f"dinner={stats['dinner']}, "
            f"snack={stats['snack']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
