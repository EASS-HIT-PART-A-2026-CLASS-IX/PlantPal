from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Plant, PlantCreate, PlantUpdate
from app.services.care_events import log_event


def _hours_since_watered(plant: Plant) -> float | None:
    if not plant.last_watered:
        return None
    try:
        watered = datetime.fromisoformat(plant.last_watered)
        if watered.tzinfo is None:
            watered = watered.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - watered).total_seconds() / 3600
    except ValueError:
        return None


_SEVERITY = {"healthy": 0, "needs_attention": 1, "critical": 2}


def _refresh_health(session: Session, plant: Plant) -> Plant:
    """Degrade health when overdue; never auto-heal (only watering heals)."""
    hours = _hours_since_watered(plant)
    if hours is None:
        return plant

    freq = plant.water_frequency_hours
    overdue_hours = hours - freq

    if overdue_hours > freq * 0.5:
        new_status = "critical"
    elif overdue_hours > 0:
        new_status = "needs_attention"
    else:
        return plant

    current_severity = _SEVERITY.get(plant.health_status, 0)
    new_severity = _SEVERITY.get(new_status, 0)

    if new_severity > current_severity:
        old_status = plant.health_status
        plant.health_status = new_status
        session.add(plant)
        log_event(
            session,
            plant_id=plant.id,
            event_type="health_changed",
            detail=f"{old_status} -> {new_status}",
        )
        session.commit()
        session.refresh(plant)

    return plant


def create_plant(session: Session, payload: PlantCreate) -> Plant:
    if not payload.last_watered:
        payload.last_watered = datetime.now(timezone.utc).isoformat()

    if not payload.image_url:
        safe = payload.name.replace(" ", "+")
        payload.image_url = (
            f"https://api.dicebear.com/7.x/identicon/svg?seed={safe}"
        )

    db_plant = Plant.model_validate(payload)
    session.add(db_plant)
    session.commit()
    session.refresh(db_plant)
    return db_plant


def list_plants(session: Session, *, skip: int = 0, limit: int = 100) -> list[Plant]:
    plants = list(session.exec(select(Plant).offset(skip).limit(limit)).all())
    return [_refresh_health(session, p) for p in plants]


def get_plant(session: Session, plant_id: int) -> Plant:
    plant = session.get(Plant, plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    return _refresh_health(session, plant)


def update_plant(session: Session, plant_id: int, payload: PlantCreate) -> Plant:
    db_plant = session.get(Plant, plant_id)
    if not db_plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    for key, value in payload.model_dump().items():
        setattr(db_plant, key, value)

    session.add(db_plant)
    session.commit()
    session.refresh(db_plant)
    return db_plant


def patch_plant(session: Session, plant_id: int, payload: PlantUpdate) -> Plant:
    db_plant = session.get(Plant, plant_id)
    if not db_plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    updates = payload.model_dump(exclude_unset=True)

    watering = "last_watered" in updates

    if watering and db_plant.health_status in ("needs_attention", "critical"):
        if "health_status" not in updates:
            updates["health_status"] = "healthy"

    for key, value in updates.items():
        setattr(db_plant, key, value)

    session.add(db_plant)

    if watering:
        log_event(session, plant_id=db_plant.id, event_type="watered")

    session.commit()
    session.refresh(db_plant)
    return db_plant


def delete_plant(session: Session, plant_id: int) -> None:
    db_plant = session.get(Plant, plant_id)
    if not db_plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    session.delete(db_plant)
    session.commit()
