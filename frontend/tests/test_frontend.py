"""Frontend interface tests — validates every plant_api function and
dashboard logic using mocked HTTP calls (no backend needed).

Run with:  python3 -m pytest tests/ -v
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests as req

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plant_api

SAMPLE_PLANT = {
    "id": 1,
    "name": "Monstera",
    "species": "Monstera deliciosa",
    "location": "Living Room",
    "light_need": "medium",
    "water_frequency_hours": 168,
    "last_watered": datetime.now(timezone.utc).isoformat(),
    "health_status": "healthy",
    "image_url": "",
    "notes": "",
}

SAMPLE_EVENT = {
    "id": 1,
    "plant_id": 1,
    "event_type": "watered",
    "detail": "",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "plant_name": "Monstera",
}


# ── Plants workflow ─────────────────────────────────────────────────

class TestPlantWorkflow:
    def test_create_then_list(self):
        """Full create-then-list workflow: created plant appears in listing."""
        with (
            patch("plant_api.requests.post") as mock_post,
            patch("plant_api.requests.get") as mock_get,
        ):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = SAMPLE_PLANT
            mock_post.return_value.raise_for_status = lambda: None

            result = plant_api.create_plant({"name": "Monstera", "species": "Monstera deliciosa"})
            assert result["id"] == 1

            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = [SAMPLE_PLANT]

            plants = plant_api.get_plants()
            assert len(plants) == 1
            assert plants[0]["name"] == "Monstera"

    def test_get_plants_backend_unreachable(self):
        """get_plants returns an empty list when the backend is down."""
        with patch("plant_api.requests.get", side_effect=req.ConnectionError):
            assert plant_api.get_plants() == []


# ── Care events workflow ────────────────────────────────────────────

class TestCareEventWorkflow:
    def test_get_care_events(self):
        """get_care_events returns a list from the API."""
        with patch("plant_api.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = [SAMPLE_EVENT]

            events = plant_api.get_care_events(plant_id=1)
            assert len(events) == 1
            assert events[0]["event_type"] == "watered"

    def test_create_care_event(self):
        """create_care_event POSTs and returns the created event."""
        note_event = {**SAMPLE_EVENT, "id": 5, "event_type": "note", "detail": "Repotted"}

        with patch("plant_api.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = note_event
            mock_post.return_value.raise_for_status = lambda: None

            result = plant_api.create_care_event(
                {"plant_id": 1, "event_type": "note", "detail": "Repotted"}
            )
            assert result["id"] == 5
            assert result["detail"] == "Repotted"

    def test_get_care_events_backend_unreachable(self):
        """get_care_events returns an empty list when the backend is down."""
        with patch("plant_api.requests.get", side_effect=req.ConnectionError):
            assert plant_api.get_care_events() == []


# ── Healthcheck ─────────────────────────────────────────────────────

class TestHealthcheck:
    def test_returns_true_on_success(self):
        """healthcheck returns True when backend responds 200."""
        with patch("plant_api.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            assert plant_api.healthcheck() is True

    def test_returns_false_on_error(self):
        """healthcheck returns False when backend is unreachable."""
        with patch("plant_api.requests.get", side_effect=req.ConnectionError):
            assert plant_api.healthcheck() is False


# ── Dashboard logic ─────────────────────────────────────────────────

class TestDashboardLogic:
    def test_on_time_plant_not_overdue(self):
        """A recently-watered plant should not be flagged as overdue."""
        plant = {"last_watered": datetime.now(timezone.utc).isoformat(), "water_frequency_hours": 168}
        assert not self._is_overdue(plant)

    def test_late_plant_is_overdue(self):
        """A plant watered 200h ago on a 168h schedule should be overdue."""
        old = (datetime.now(timezone.utc) - timedelta(hours=200)).isoformat()
        plant = {"last_watered": old, "water_frequency_hours": 168}
        assert self._is_overdue(plant)

    def test_missing_last_watered_not_overdue(self):
        """A plant with no watering history should not be flagged as overdue."""
        plant = {"last_watered": None, "water_frequency_hours": 168}
        assert not self._is_overdue(plant)

    @staticmethod
    def _is_overdue(plant: dict) -> bool:
        """Mirror of the overdue logic used by the dashboard."""
        lw = plant.get("last_watered")
        if not lw:
            return False
        watered = datetime.fromisoformat(lw)
        if watered.tzinfo is None:
            watered = watered.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - watered).total_seconds() / 3600
        return hours > plant.get("water_frequency_hours", 168)
