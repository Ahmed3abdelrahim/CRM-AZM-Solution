from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def get_health(session: AsyncSession = Depends(get_session)) -> dict:
    database_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    return {"status": "ok", "database": database_status}
