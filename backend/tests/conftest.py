import os
from pathlib import Path


def _load_env_test() -> None:
    """Loads KEY=VALUE lines from backend/.env.test (git-ignored) so local
    credentials never live in the repository."""
    env_file = Path(__file__).resolve().parent.parent / ".env.test"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env_test()

# The whole platform runs on PostgreSQL — tests included. A dedicated
# database keeps them isolated from the dev data. Point at your server via
# TEST_DATABASE_URL (env var or backend/.env.test); the fallback matches a
# stock local PostgreSQL install.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/digital_app_test",
)
if not TEST_DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("Tests run on PostgreSQL only; set TEST_DATABASE_URL accordingly")

# Test environment must be configured before app modules import settings.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("JWT_SECRET", "test-only-secret-key-0123456789abcdef")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("LOCAL_STORAGE_DIR", "./.pytest_storage")
os.environ.setdefault("MEDIA_PROCESSING_INLINE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

_pg_schema_ready = False


def _ensure_test_database() -> None:
    """Creates the dedicated test database if it does not exist yet."""
    import asyncio
    from urllib.parse import unquote, urlsplit

    import asyncpg

    parts = urlsplit(TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql"))
    db_name = parts.path.lstrip("/")

    async def create() -> None:
        conn = await asyncpg.connect(
            host=parts.hostname,
            port=parts.port or 5432,
            user=unquote(parts.username or "postgres"),
            password=unquote(parts.password or ""),
            database="postgres",
        )
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
        await conn.close()

    asyncio.run(create())


@pytest.fixture(scope="session", autouse=True)
def clean_test_storage():
    """Provision the test DB and wipe the local-storage dir once per run."""
    import shutil

    _ensure_test_database()
    shutil.rmtree("./.pytest_storage", ignore_errors=True)
    yield
    shutil.rmtree("./.pytest_storage", ignore_errors=True)


@pytest.fixture
async def db_engine():
    # NullPool: each test runs in its own event loop; pooled asyncpg
    # connections must not leak across loops. The schema is rebuilt once per
    # process; tests are isolated by truncating every table. The test
    # database must not be shared by concurrent runs.
    from sqlalchemy import text

    global _pg_schema_ready
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        if not _pg_schema_ready:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            _pg_schema_ready = True
        else:
            tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))  # noqa: S608
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def seeded(db_engine):
    """Seeds permissions, system roles and the demo tenant into the test DB."""
    from app.seed import run_seed

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await run_seed(session, include_demo=True)
        await session.commit()


async def login(client, email: str, password: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def bearer(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def admin_tokens(client, seeded) -> dict:
    return await login(client, "admin@demo-org.com", "Admin@12345")


@pytest.fixture
async def client(db_engine):
    app = create_app()
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
