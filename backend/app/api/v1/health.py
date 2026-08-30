from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.envelope import success

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness: process is up."""
    return success({"status": "ok"})


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness: dependencies reachable."""
    await db.execute(text("SELECT 1"))
    return success({"status": "ready", "database": "ok"})
