from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def get_customer_phone_mask_by_id(session: AsyncSession, customer_id: int) -> str | None:
    result = await session.execute(
        text("SELECT phone_mask FROM customers WHERE customer_id = :cid"),
        {"cid": customer_id}
    )
    row = result.fetchone()
    return row[0] if row else None


async def get_customer_name_by_id(session: AsyncSession, customer_id: int) -> str | None:
    """customers 테이블에서 customer_id로 이름만 조회."""
    result = await session.execute(
        text("SELECT name FROM customers WHERE customer_id = :cid"),
        {"cid": customer_id}
    )
    row = result.fetchone()
    return row[0] if row else None
