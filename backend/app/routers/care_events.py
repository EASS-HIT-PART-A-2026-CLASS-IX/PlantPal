from fastapi import APIRouter

from app.db import SessionDep
from app.models import CareEventCreate, CareEventRead
from app.services import care_events as service

router = APIRouter(prefix="/care-events", tags=["care-events"])


@router.get("/", response_model=list[CareEventRead])
def list_care_events(
    session: SessionDep,
    plant_id: int | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[CareEventRead]:
    return service.list_events(
        session, plant_id=plant_id, event_type=event_type, limit=limit
    )


@router.post("/", response_model=CareEventRead)
def create_care_event(
    payload: CareEventCreate, session: SessionDep
) -> CareEventRead:
    return service.create_event(session, payload)
