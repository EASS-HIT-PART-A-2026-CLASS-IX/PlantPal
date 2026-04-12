from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import CareEvent, CareEventCreate, CareEventRead, Plant


def _enrich(session: Session, event: CareEvent) -> CareEventRead:
    """Attach the plant name to a raw CareEvent row."""
    plant = session.get(Plant, event.plant_id)
    return CareEventRead(
        id=event.id,
        plant_id=event.plant_id,
        event_type=event.event_type,
        detail=event.detail,
        created_at=event.created_at,
        plant_name=plant.name if plant else None,
    )


def list_events(
    session: Session,
    *,
    plant_id: int | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[CareEventRead]:
    stmt = select(CareEvent)
    if plant_id is not None:
        stmt = stmt.where(CareEvent.plant_id == plant_id)
    if event_type is not None:
        stmt = stmt.where(CareEvent.event_type == event_type)
    stmt = stmt.order_by(CareEvent.id.desc()).limit(limit)  # type: ignore[union-attr]
    rows = list(session.exec(stmt).all())
    return [_enrich(session, r) for r in rows]


def create_event(session: Session, payload: CareEventCreate) -> CareEventRead:
    plant = session.get(Plant, payload.plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    db_event = CareEvent(
        plant_id=payload.plant_id,
        event_type=payload.event_type,
        detail=payload.detail,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(db_event)
    session.commit()
    session.refresh(db_event)
    return _enrich(session, db_event)


def log_event(
    session: Session,
    *,
    plant_id: int,
    event_type: str,
    detail: str = "",
) -> None:
    """Internal helper used by the plants service to auto-log events."""
    db_event = CareEvent(
        plant_id=plant_id,
        event_type=event_type,
        detail=detail,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(db_event)
