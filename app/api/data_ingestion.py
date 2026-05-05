from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_dispatcher
from app.db.session import get_db
from app.models.service import ServiceReport
from app.models.user import User
from app.schemas.data_ingestion import ServiceImportRequest, ServiceImportResponse, ServiceReportCreate, ServiceReportOut, ServiceReportReview
from app.services.data_ingestion import approve_service_report, create_user_service_report, upsert_emergency_services

router = APIRouter()


@router.post("/services/import", response_model=ServiceImportResponse)
async def import_services(
    payload: ServiceImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_dispatcher),
):
    inserted, rejected, warnings = await upsert_emergency_services(db, payload.services, source=payload.source, dry_run=payload.dry_run)
    return ServiceImportResponse(
        source=payload.source,
        dry_run=payload.dry_run,
        received=len(payload.services),
        inserted_or_updated=inserted,
        rejected=rejected,
        warnings=warnings,
    )


@router.post("/services/report", response_model=ServiceReportOut)
async def report_service(
    payload: ServiceReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_user_service_report(db, current_user.id, payload)


@router.patch("/services/report/{report_id}", response_model=ServiceReportOut)
async def review_service_report(
    report_id: UUID,
    payload: ServiceReportReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_dispatcher),
):
    result = await db.execute(select(ServiceReport).where(ServiceReport.id == report_id))
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Service report not found")
    if payload.status == "approved":
        await approve_service_report(db, report, payload.confidence_score)
        await db.refresh(report)
    else:
        report.verification_status = "rejected"
        await db.commit()
        await db.refresh(report)
    return report
