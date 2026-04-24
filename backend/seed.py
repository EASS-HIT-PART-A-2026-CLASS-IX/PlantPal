"""
Seed the running PlantPal API with diverse sample data.

Creates 8 plants across every location, light level, and health status,
with realistic watering histories and care events so both the Dashboard
and Care Log have meaningful content to display.
"""

import os
from datetime import datetime, timedelta, timezone

import httpx

API = os.getenv("API_URL", "http://localhost:8000")
_USERNAME = os.getenv("DEFAULT_EDITOR_USERNAME", "gardener")
_PASSWORD = os.getenv("DEFAULT_EDITOR_PASSWORD", "plantpal")

now = datetime.now(timezone.utc)


def _get_token() -> dict:
    """Obtain an editor JWT, fall back to empty headers if auth isn't up yet."""
    try:
        resp = httpx.post(
            f"{API}/token",
            data={"username": _USERNAME, "password": _PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5,
        )
        if resp.status_code == 200:
            return {"Authorization": f"Bearer {resp.json()['access_token']}"}
    except Exception:
        pass
    return {}


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ── Plants ────────────────────────────────────────────────────────────
# Designed so every filter/field combination is represented at least once:
#   locations:  Living Room, Bedroom, Kitchen, Bathroom, Balcony, Office
#   light:      low, medium, high
#   health:     healthy, needs_attention, critical
#   frequency:  from 48h (2 days) to 504h (21 days)
#   last_watered: ranges from "just now" to "weeks ago" to trigger overdue

PLANTS = [
    {
        "name": "Monstera",
        "species": "Monstera deliciosa",
        "location": "Living Room",
        "light_need": "medium",
        "water_frequency_hours": 168,
        "health_status": "healthy",
        "last_watered": _iso(now - timedelta(hours=20)),
        "notes": "Loves humidity and indirect light",
    },
    {
        "name": "Snake Plant",
        "species": "Dracaena trifasciata",
        "location": "Bedroom",
        "light_need": "low",
        "water_frequency_hours": 336,
        "health_status": "healthy",
        "last_watered": _iso(now - timedelta(days=10)),
        "notes": "Very low maintenance, almost impossible to kill",
    },
    {
        "name": "Basil",
        "species": "Ocimum basilicum",
        "location": "Kitchen",
        "light_need": "high",
        "water_frequency_hours": 48,
        "health_status": "needs_attention",
        "last_watered": _iso(now - timedelta(hours=60)),
        "notes": "Needs frequent watering, wilts fast in heat",
    },
    {
        "name": "Peace Lily",
        "species": "Spathiphyllum wallisii",
        "location": "Bathroom",
        "light_need": "low",
        "water_frequency_hours": 120,
        "health_status": "critical",
        "last_watered": _iso(now - timedelta(days=14)),
        "notes": "Drooping leaves, needs water urgently",
    },
    {
        "name": "Fiddle Leaf Fig",
        "species": "Ficus lyrata",
        "location": "Living Room",
        "light_need": "high",
        "water_frequency_hours": 168,
        "health_status": "needs_attention",
        "last_watered": _iso(now - timedelta(days=9)),
        "notes": "Sensitive to drafts and overwatering",
    },
    {
        "name": "Pothos",
        "species": "Epipremnum aureum",
        "location": "Office",
        "light_need": "low",
        "water_frequency_hours": 240,
        "health_status": "healthy",
        "last_watered": _iso(now - timedelta(days=5)),
        "notes": "Great trailing plant for shelves",
    },
    {
        "name": "Aloe Vera",
        "species": "Aloe barbadensis",
        "location": "Balcony",
        "light_need": "high",
        "water_frequency_hours": 504,
        "health_status": "healthy",
        "last_watered": _iso(now - timedelta(days=18)),
        "notes": "Medicinal gel inside leaves, don't overwater",
    },
    {
        "name": "Fern",
        "species": "Nephrolepis exaltata",
        "location": "Bedroom",
        "light_need": "medium",
        "water_frequency_hours": 72,
        "health_status": "healthy",
        "last_watered": _iso(now - timedelta(hours=10)),
        "notes": "Mist daily for best results",
    },
]


# ── Care Events ───────────────────────────────────────────────────────
# Builds a realistic history so the Care Log timeline, streaks, and
# per-plant drilldown all have data to render.

def _build_care_events(plant_ids: dict[str, int]) -> list[dict]:
    """Build care-event payloads for every seeded plant.

    Each dict contains the standard API fields (``plant_id``,
    ``event_type``, ``detail``) plus a private ``_ago`` timedelta that
    ``main()`` converts into an absolute ``created_at`` timestamp before
    POSTing.  This keeps the data definition readable ("6 days ago")
    without hard-coding dates.
    """
    pid = plant_ids

    events = [
        # --- Monstera: well-cared-for, multiple waterings over the past week ---
        {"plant_id": pid["Monstera"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=6)},
        {"plant_id": pid["Monstera"], "event_type": "note", "detail": "New leaf unfurling!",
         "_ago": timedelta(days=5)},
        {"plant_id": pid["Monstera"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=3)},
        {"plant_id": pid["Monstera"], "event_type": "watered", "detail": "",
         "_ago": timedelta(hours=20)},

        # --- Snake Plant: barely needs attention, one watering long ago ---
        {"plant_id": pid["Snake Plant"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=10)},
        {"plant_id": pid["Snake Plant"], "event_type": "note", "detail": "Rotated pot 180 degrees",
         "_ago": timedelta(days=4)},

        # --- Basil: high-frequency, missed a watering, health degraded ---
        {"plant_id": pid["Basil"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=4)},
        {"plant_id": pid["Basil"], "event_type": "watered", "detail": "",
         "_ago": timedelta(hours=60)},
        {"plant_id": pid["Basil"], "event_type": "health_changed",
         "detail": "healthy -> needs_attention", "_ago": timedelta(hours=10)},
        {"plant_id": pid["Basil"], "event_type": "note",
         "detail": "Leaves turning yellow at the base", "_ago": timedelta(hours=8)},

        # --- Peace Lily: neglected, went critical ---
        {"plant_id": pid["Peace Lily"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=14)},
        {"plant_id": pid["Peace Lily"], "event_type": "health_changed",
         "detail": "healthy -> needs_attention", "_ago": timedelta(days=8)},
        {"plant_id": pid["Peace Lily"], "event_type": "health_changed",
         "detail": "needs_attention -> critical", "_ago": timedelta(days=4)},
        {"plant_id": pid["Peace Lily"], "event_type": "note",
         "detail": "Leaves completely drooping, soil bone dry",
         "_ago": timedelta(days=2)},

        # --- Fiddle Leaf Fig: inconsistent care ---
        {"plant_id": pid["Fiddle Leaf Fig"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=16)},
        {"plant_id": pid["Fiddle Leaf Fig"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=9)},
        {"plant_id": pid["Fiddle Leaf Fig"], "event_type": "health_changed",
         "detail": "healthy -> needs_attention", "_ago": timedelta(days=2)},
        {"plant_id": pid["Fiddle Leaf Fig"], "event_type": "note",
         "detail": "Brown spots on lower leaves, possible overwatering last time",
         "_ago": timedelta(days=1)},

        # --- Pothos: steady, on schedule, moved rooms ---
        {"plant_id": pid["Pothos"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=15)},
        {"plant_id": pid["Pothos"], "event_type": "edited",
         "detail": "location: Kitchen -> Office", "_ago": timedelta(days=12)},
        {"plant_id": pid["Pothos"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=5)},
        {"plant_id": pid["Pothos"], "event_type": "note",
         "detail": "Propagated 3 cuttings into water", "_ago": timedelta(days=3)},

        # --- Aloe Vera: infrequent but fine, adjusted schedule ---
        {"plant_id": pid["Aloe Vera"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=18)},
        {"plant_id": pid["Aloe Vera"], "event_type": "edited",
         "detail": "water frequency: 336 -> 504", "_ago": timedelta(days=12)},
        {"plant_id": pid["Aloe Vera"], "event_type": "note",
         "detail": "Harvested one leaf for a burn", "_ago": timedelta(days=7)},

        # --- Fern: frequent waterer, today's streak contributor ---
        {"plant_id": pid["Fern"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=3)},
        {"plant_id": pid["Fern"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=2)},
        {"plant_id": pid["Fern"], "event_type": "watered", "detail": "",
         "_ago": timedelta(days=1)},
        {"plant_id": pid["Fern"], "event_type": "watered", "detail": "",
         "_ago": timedelta(hours=10)},
        {"plant_id": pid["Fern"], "event_type": "note",
         "detail": "Misted leaves, humidity was low today",
         "_ago": timedelta(hours=10)},
    ]

    return events


def main() -> None:
    """Seed the running API with sample plants and care events.

    Idempotent: skips entirely if any plants already exist.  Requires
    the backend to be running at ``API`` (default ``localhost:8000``).
    Events are sorted chronologically before insertion so the Care Log
    timeline renders in the expected order.
    """
    auth_headers = _get_token()

    existing = httpx.get(f"{API}/plants/").json()
    if existing:
        print(f"Database already has {len(existing)} plants, skipping seed.")
        return

    # ── Create plants ─────────────────────────────────────────────────
    plant_ids: dict[str, int] = {}
    for plant in PLANTS:
        resp = httpx.post(f"{API}/plants/", json=plant, headers=auth_headers)
        resp.raise_for_status()
        created = resp.json()
        plant_ids[plant["name"]] = created["id"]
        print(f"  + {plant['name']} (id={created['id']})")

    print(f"\nSeeded {len(PLANTS)} plants.")

    # ── Create care events ────────────────────────────────────────────
    # Convert relative _ago deltas into absolute ISO timestamps
    events = _build_care_events(plant_ids)
    for e in events:
        ago = e.pop("_ago")
        e["created_at"] = _iso(now - ago)

    events.sort(key=lambda x: x["created_at"])

    count = 0
    for e in events:
        resp = httpx.post(f"{API}/care-events/", json=e)
        resp.raise_for_status()
        count += 1

    print(f"Seeded {count} care events.\n")

    # ── Summary ───────────────────────────────────────────────────────
    print("Scenario coverage:")
    print("  Locations:  Living Room, Bedroom, Kitchen, Bathroom, Balcony, Office")
    print("  Light:      low, medium, high")
    print("  Health:     healthy (4), needs_attention (2), critical (1)")
    print("  Overdue:    Basil (60h on 48h cycle), Peace Lily (14d on 5d cycle),")
    print("              Fiddle Leaf Fig (9d on 7d cycle)")
    print("  On track:   Monstera, Snake Plant, Pothos, Aloe Vera, Fern")
    print("  Streak:     Fern has 4 consecutive days of watering")
    print("  Edits:      2 edit events (location change, frequency change)")
    print("  Care notes: 8 notes across different plants")
    print("  Timeline:   30 events spanning the last 18 days")


if __name__ == "__main__":
    main()
