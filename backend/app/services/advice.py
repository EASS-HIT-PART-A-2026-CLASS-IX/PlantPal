"""Plant advice proxy.

Calls the ``ai_service`` FastAPI microservice; if it's unreachable,
falls back to a deterministic rule-based advice so the stack still runs
end-to-end without any LLM configured.
"""

from __future__ import annotations

import logging

import httpx

from app.cache import cache_get, cache_set
from app.config import get_settings
from app.models import Plant

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 min


def _fallback_advice(plant: Plant) -> dict:
    tips: list[str] = []
    if plant.health_status == "critical":
        tips.append("Water immediately and move to indirect light.")
    elif plant.health_status == "needs_attention":
        tips.append("Water soon and check the soil moisture.")
    else:
        tips.append("Keep following the current schedule — looking good!")

    if plant.light_need == "high":
        tips.append("Place near a south-facing window for 6+ hours of bright light.")
    elif plant.light_need == "low":
        tips.append("Avoid direct sun; bright indirect light is plenty.")
    else:
        tips.append("Medium indirect light suits this plant well.")

    if plant.water_frequency_hours >= 168:
        tips.append("Let the top inch of soil dry out between waterings.")
    else:
        tips.append("Check moisture every couple of days — it likes humidity.")

    return {
        "plant_id": plant.id,
        "plant_name": plant.name,
        "summary": f"Care tips for your {plant.species} ({plant.health_status}).",
        "tips": tips,
        "source": "fallback",
    }


async def get_advice(plant: Plant) -> dict:
    settings = get_settings()
    cache_key = f"plants:advice:{plant.id}:{plant.health_status}"
    if settings.cache_enabled:
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

    payload = {
        "id": plant.id,
        "name": plant.name,
        "species": plant.species,
        "location": plant.location,
        "light_need": plant.light_need,
        "water_frequency_hours": plant.water_frequency_hours,
        "health_status": plant.health_status,
        "last_watered": plant.last_watered,
        "notes": plant.notes,
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.ai_service_url, timeout=settings.ai_service_timeout
        ) as client:
            resp = await client.post("/advice", json=payload)
            resp.raise_for_status()
            advice = resp.json()
    except Exception as exc:
        logger.info("ai-service-unreachable err=%s — using fallback", exc)
        advice = _fallback_advice(plant)

    if settings.cache_enabled:
        await cache_set(cache_key, advice, ttl=_CACHE_TTL)
    return advice
