from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def get_user_name_by_id(session: AsyncSession, user_id: int) -> str | None:
    result = await session.execute(
        text("SELECT name FROM users WHERE user_id = :uid"),
        {"uid": user_id}
    )
    row = result.fetchone()
    return row[0] if row else None
