from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.models.volunteer import Volunteer


async def recompute_volunteer_rating(db: AsyncSession, volunteer_id) -> None:
    result = await db.execute(
        select(func.avg(Feedback.rating), func.count(Feedback.id)).where(Feedback.volunteer_id == volunteer_id)
    )
    avg_rating, count = result.one()
    if avg_rating is None:
        return
    # Bayesian-ish smoothing to avoid one 5-star rating dominating ranking.
    smoothed = ((3.5 * 5) + (float(avg_rating) * int(count))) / (5 + int(count))
    await db.execute(
        update(Volunteer)
        .where(Volunteer.id == volunteer_id)
        .values(rating=round(smoothed, 2), completed_responses=Volunteer.completed_responses + 1)
    )
