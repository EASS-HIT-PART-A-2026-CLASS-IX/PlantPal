from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Plant, PlantCreate, PlantUpdate


def create_plant(session: Session, payload: PlantCreate) -> Plant:
    if not payload.last_watered:
        payload.last_watered = date.today().isoformat()

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
    return list(session.exec(select(Plant).offset(skip).limit(limit)).all())


def get_plant(session: Session, plant_id: int) -> Plant:
    plant = session.get(Plant, plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plant


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

    # Watering a plant that needs attention resets health to healthy
    if "last_watered" in updates and db_plant.health_status in ("needs_attention", "critical"):
        if "health_status" not in updates:
            updates["health_status"] = "healthy"

    for key, value in updates.items():
        setattr(db_plant, key, value)

    session.add(db_plant)
    session.commit()
    session.refresh(db_plant)
    return db_plant


def delete_plant(session: Session, plant_id: int) -> None:
    db_plant = session.get(Plant, plant_id)
    if not db_plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    session.delete(db_plant)
    session.commit()
