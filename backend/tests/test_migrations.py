from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


TEST_MIGRATION_DB_URL_ENV = "TEST_POSTGRES_MIGRATIONS_DATABASE_URL"


@pytest.mark.skipif(
    not os.getenv(TEST_MIGRATION_DB_URL_ENV),
    reason=f"{TEST_MIGRATION_DB_URL_ENV} is not set",
)
def test_alembic_upgrade_head_on_clean_postgres() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = env[TEST_MIGRATION_DB_URL_ENV]

    downgrade = subprocess.run(
        [".venv/bin/alembic", "downgrade", "base"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert downgrade.returncode == 0, downgrade.stderr or downgrade.stdout

    upgrade = subprocess.run(
        [".venv/bin/alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout
