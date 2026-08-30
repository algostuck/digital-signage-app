"""Schema parity: the Alembic migration chain must produce exactly the
schema the models declare — verified on PostgreSQL, the only engine the
platform runs on.

The API test suite builds its schema with Base.metadata.create_all, so a
column added to a model but missed in a migration (or vice versa) passes
every functional test and then fails in a real, migrated database. This
test runs the full migration chain on a scratch PostgreSQL database and
diffs the resulting tables/columns against the model metadata.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401 (populate Base.metadata)
from app.db.base import Base
from tests.conftest import TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[1]
PARITY_DB = "digital_app_parity"


def _parity_url() -> str:
    parts = urlsplit(TEST_DATABASE_URL)
    return TEST_DATABASE_URL.replace(parts.path, f"/{PARITY_DB}")


def _recreate_parity_database() -> None:
    import asyncpg

    parts = urlsplit(TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql"))

    async def recreate() -> None:
        conn = await asyncpg.connect(
            host=parts.hostname,
            port=parts.port or 5432,
            user=unquote(parts.username or "postgres"),
            password=unquote(parts.password or ""),
            database="postgres",
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{PARITY_DB}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{PARITY_DB}"')
        await conn.close()

    asyncio.run(recreate())


@pytest.fixture
def migrated_postgres() -> str:
    _recreate_parity_database()
    url = _parity_url()
    env = {
        **os.environ,
        "DATABASE_URL": url,
        "ENVIRONMENT": "test",
        "JWT_SECRET": "test-only-secret-key-0123456789abcdef",
    }
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"alembic upgrade failed:\n{result.stderr}"
    return url


async def _collect_schema(url: str) -> dict[str, dict]:
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as conn:

        def read(sync_conn):
            inspector = inspect(sync_conn)
            return {
                table: {
                    column["name"]: bool(column["nullable"])
                    for column in inspector.get_columns(table)
                }
                for table in inspector.get_table_names()
                if table != "alembic_version"
            }

        schema = await conn.run_sync(read)
    await engine.dispose()
    return schema


async def test_migrated_schema_matches_models(migrated_postgres):
    migrated = await _collect_schema(migrated_postgres)
    model_tables = set(Base.metadata.tables)

    assert set(migrated) == model_tables, (
        f"tables only in migrations: {sorted(set(migrated) - model_tables)}; "
        f"tables only in models: {sorted(model_tables - set(migrated))}"
    )

    problems = []
    for table_name in sorted(model_tables):
        migrated_cols = migrated[table_name]
        model_cols = Base.metadata.tables[table_name].columns
        only_migration = set(migrated_cols) - {c.name for c in model_cols}
        only_model = {c.name for c in model_cols} - set(migrated_cols)
        if only_migration:
            problems.append(f"{table_name}: columns only in migration {sorted(only_migration)}")
        if only_model:
            problems.append(f"{table_name}: columns only in model {sorted(only_model)}")
        for column in model_cols:
            if column.name in migrated_cols and migrated_cols[column.name] != bool(
                column.nullable
            ):
                problems.append(
                    f"{table_name}.{column.name}: nullable is "
                    f"{migrated_cols[column.name]} in migration but "
                    f"{column.nullable} in model"
                )
    assert not problems, "\n".join(problems)
