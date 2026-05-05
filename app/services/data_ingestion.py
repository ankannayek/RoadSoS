from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List
from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import EmergencyService, ServiceReport
from app.schemas.data_ingestion import EmergencyServiceIn, ServiceReportCreate

VALID_SERVICE_TYPES = {"AMBULANCE", "TRAUMA", "HOSPITAL", "POLICE", "FIRE", "TOWING", "MECHANIC"}
SOURCE_BASE_CONFIDENCE = {
    "gov": 0.9,
    "nhai": 0.88,
    "osm": 0.72,
    "partner": 0.82,
    "manual": 0.7,
    "seed": 0.55,
    "user_report": 0.45,
}


def normalize_type(value: str) -> str:
    cleaned = value.strip().upper().replace(" ", "_")
    if cleaned in {"HOSPITAL", "CLINIC", "TRAUMA_CENTER"}:
        return "TRAUMA" if cleaned == "TRAUMA_CENTER" else cleaned
    return cleaned


def confidence_for(source: str, provided: float) -> float:
    base = SOURCE_BASE_CONFIDENCE.get(source, 0.5)
    return round(max(0.05, min(0.99, (base * 0.65) + (provided * 0.35))), 3)


def dedupe_key(record: EmergencyServiceIn) -> str:
    raw = f"{record.name.lower().strip()}|{normalize_type(record.type)}|{round(record.lat, 5)}|{round(record.lng, 5)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def upsert_emergency_services(db: AsyncSession, records: Iterable[EmergencyServiceIn], source: str, dry_run: bool = False) -> tuple[int, int, list[str]]:
    inserted_or_updated = 0
    rejected = 0
    warnings: list[str] = []
    for record in records:
        service_type = normalize_type(record.type)
        if service_type not in VALID_SERVICE_TYPES:
            rejected += 1
            warnings.append(f"Rejected unsupported service type: {record.type}")
            continue
        metadata = dict(record.metadata_json or {})
        metadata["dedupe_key"] = dedupe_key(record)
        metadata["ingestion_source"] = source
        score = confidence_for(source, float(record.confidence_score))
        if dry_run:
            inserted_or_updated += 1
            continue
        result = await db.execute(
            select(EmergencyService).where(
                EmergencyService.source == source,
                EmergencyService.metadata_json["dedupe_key"].astext == metadata["dedupe_key"],
            )
        )
        service = result.scalar_one_or_none()
        if service is None:
            service = EmergencyService(
                name=record.name.strip(),
                type=service_type,
                phone=record.phone,
                lat=record.lat,
                lng=record.lng,
                location=WKTElement(f"POINT({record.lng} {record.lat})", srid=4326),
                capacity=record.capacity,
                confidence_score=score,
                source=source,
                metadata_json=metadata,
                is_active=True,
            )
            db.add(service)
        else:
            service.name = record.name.strip()
            service.type = service_type
            service.phone = record.phone
            service.lat = record.lat
            service.lng = record.lng
            service.location = WKTElement(f"POINT({record.lng} {record.lat})", srid=4326)
            service.capacity = record.capacity
            service.confidence_score = score
            service.metadata_json = metadata
            service.is_active = True
        inserted_or_updated += 1
    if not dry_run:
        await db.commit()
    return inserted_or_updated, rejected, warnings


async def create_user_service_report(db: AsyncSession, reporter_user_id: UUID, payload: ServiceReportCreate) -> ServiceReport:
    report = ServiceReport(
        reporter_user_id=reporter_user_id,
        name=payload.name.strip(),
        type=normalize_type(payload.type),
        phone=payload.phone,
        lat=payload.lat,
        lng=payload.lng,
        note=payload.note,
        verification_status="pending",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def approve_service_report(db: AsyncSession, report: ServiceReport, confidence_score: float) -> EmergencyService:
    record = EmergencyServiceIn(
        name=report.name,
        type=report.type,
        phone=report.phone,
        lat=report.lat,
        lng=report.lng,
        confidence_score=confidence_score,
        source="user_report",
        metadata_json={"service_report_id": str(report.id)},
    )
    await upsert_emergency_services(db, [record], source="user_report", dry_run=False)
    report.verification_status = "approved"
    await db.commit()
    result = await db.execute(
        select(EmergencyService).where(EmergencyService.metadata_json["service_report_id"].astext == str(report.id))
    )
    service = result.scalar_one()
    report.service_id = service.id
    await db.commit()
    return service
