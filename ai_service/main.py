"""PlantPal AI Advisor microservice.

Small FastAPI service that takes a plant payload and returns care advice.
When ``GOOGLE_API_KEY`` + ``GOOGLE_GEMINI_MODEL`` are configured, it
routes through Pydantic AI / Google Gemini; otherwise it returns a
deterministic rule-based response so the stack is always demo-ready.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="PlantPal AI Advisor", version="0.1.0")


class PlantPayload(BaseModel):
    id: int | None = None
    name: str
    species: str = ""
    location: str = "Unknown"
    light_need: str = "medium"
    water_frequency_hours: int = 168
    health_status: str = "healthy"
    last_watered: str | None = None
    notes: str = ""


class AdviceResponse(BaseModel):
    plant_id: int | None = None
    plant_name: str
    summary: str
    tips: list[str]
    source: str = "fallback"


def _rule_based_advice(plant: PlantPayload) -> AdviceResponse:
    tips: list[str] = []
    if plant.health_status == "critical":
        tips.append("Water immediately — the plant has been overdue for a while.")
        tips.append("Move out of direct sun until it recovers.")
    elif plant.health_status == "needs_attention":
        tips.append("Water within the next day and check soil moisture first.")
    else:
        tips.append("The plant looks healthy — keep the current schedule.")

    if plant.light_need == "high":
        tips.append("Aim for 6+ hours of bright indirect or gentle direct light.")
    elif plant.light_need == "low":
        tips.append("Keep away from direct sun; a north-facing window is ideal.")
    else:
        tips.append("Medium indirect light works great for this one.")

    if plant.water_frequency_hours >= 168:
        tips.append("Let the top inch of soil dry between waterings.")
    else:
        tips.append("Check moisture every 2–3 days — it prefers consistent humidity.")

    if plant.location.lower() in {"bathroom", "kitchen"}:
        tips.append("Humid rooms are a win — just avoid cold drafts.")

    return AdviceResponse(
        plant_id=plant.id,
        plant_name=plant.name,
        summary=f"Care tips for {plant.name} ({plant.species or 'unknown species'}).",
        tips=tips,
        source="rule-based",
    )


async def _llm_advice(plant: PlantPayload) -> AdviceResponse | None:
    """Try Pydantic AI + Google Gemini; return None if not configured/reachable."""
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("GOOGLE_GEMINI_MODEL")
    if not api_key or not model_name:
        return None
    try:
        from pydantic_ai import Agent
        from pydantic_ai.models.google import GoogleModel
    except ImportError:
        return None

    try:
        agent: Agent[Any, AdviceResponse] = Agent(
            model=GoogleModel(model=model_name, api_key=api_key),
            system_prompt=(
                "You are a friendly houseplant care assistant. "
                "Given structured plant data, respond with a short summary "
                "and three to five concrete care tips. "
                "Do not invent species-specific botanical facts you are unsure of."
            ),
            output_type=AdviceResponse,
        )
        result = await agent.run(plant.model_dump_json())
        response = result.output
        response.source = "gemini"
        response.plant_id = plant.id
        response.plant_name = plant.name
        return response
    except Exception:
        return None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "plantpal-ai-advisor"}


@app.post("/advice", response_model=AdviceResponse)
async def advice(plant: PlantPayload) -> AdviceResponse:
    llm_response = await _llm_advice(plant)
    if llm_response is not None:
        return llm_response
    return _rule_based_advice(plant)
