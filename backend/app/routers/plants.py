from fastapi import APIRouter, Depends, HTTPException

from app.cache import cache_get, cache_set, invalidate_plants_cache
from app.config import get_settings
from app.db import SessionDep
from app.models import PlantCreate, PlantRead, PlantUpdate
from app.security import require_role
from app.services import plants as service
from app.services import advice as advice_service

router = APIRouter(prefix="/plants", tags=["plants"])

_EDITOR = Depends(require_role("editor"))


@router.post("/", response_model=PlantRead, dependencies=[_EDITOR])
async def create_plant(payload: PlantCreate, session: SessionDep) -> PlantRead:
    plant = service.create_plant(session, payload)
    await invalidate_plants_cache()
    return plant


@router.get("/", response_model=list[PlantRead])
async def list_plants(session: SessionDep, skip: int = 0, limit: int = 100) -> list[PlantRead]:
    settings = get_settings()
    cache_key = f"plants:list:{skip}:{limit}"
    if settings.cache_enabled:
        cached = await cache_get(cache_key)
        if cached is not None:
            # Deserialize back into validated PlantRead objects so FastAPI's
            # response_model serializer never sees raw dicts.
            try:
                return [PlantRead.model_validate(p) for p in cached]
            except Exception:
                # Stale / incompatible cache entry — fall through to DB
                pass

    plants = service.list_plants(session, skip=skip, limit=limit)
    if settings.cache_enabled:
        await cache_set(
            cache_key,
            [p.model_dump() for p in plants],
            ttl=settings.cache_ttl_seconds,
        )
    return plants


@router.get("/{plant_id}", response_model=PlantRead)
def get_plant(plant_id: int, session: SessionDep) -> PlantRead:
    return service.get_plant(session, plant_id)


@router.put("/{plant_id}", response_model=PlantRead, dependencies=[_EDITOR])
async def update_plant(plant_id: int, payload: PlantCreate, session: SessionDep) -> PlantRead:
    plant = service.update_plant(session, plant_id, payload)
    await invalidate_plants_cache()
    return plant


@router.patch("/{plant_id}", response_model=PlantRead, dependencies=[_EDITOR])
async def patch_plant(plant_id: int, payload: PlantUpdate, session: SessionDep) -> PlantRead:
    plant = service.patch_plant(session, plant_id, payload)
    await invalidate_plants_cache()
    return plant


@router.delete("/{plant_id}", dependencies=[_EDITOR])
async def delete_plant(plant_id: int, session: SessionDep) -> dict:
    service.delete_plant(session, plant_id)
    await invalidate_plants_cache()
    return {"detail": "Plant deleted successfully"}


@router.get("/{plant_id}/advice")
async def plant_advice(plant_id: int, session: SessionDep) -> dict:
    plant = service.get_plant(session, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    return await advice_service.get_advice(plant)
