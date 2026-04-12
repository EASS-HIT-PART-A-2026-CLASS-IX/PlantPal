import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plant_api  # noqa: E402


def test_create_then_list_workflow():
    """After creating a plant via the API client, it should appear in the list."""
    created = {
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

    with (
        patch("plant_api.requests.post") as mock_post,
        patch("plant_api.requests.get") as mock_get,
    ):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = created
        mock_post.return_value.raise_for_status = lambda: None

        result = plant_api.create_plant({"name": "Monstera", "species": "Monstera deliciosa"})
        assert result["id"] == 1

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [created]

        plants = plant_api.get_plants()
        assert len(plants) == 1
        assert plants[0]["name"] == "Monstera"


def test_backend_unreachable_returns_empty():
    """When the backend is down, get_plants should return an empty list."""
    import requests as req

    with patch("plant_api.requests.get", side_effect=req.ConnectionError):
        plants = plant_api.get_plants()
        assert plants == []


def test_overdue_metric_calculation():
    """Verify the overdue detection logic used by the dashboard (hours-based)."""
    now = datetime.now(timezone.utc)
    recent = now.isoformat()
    old = (now - timedelta(hours=200)).isoformat()

    plant_ok = {"last_watered": recent, "water_frequency_hours": 168}
    plant_overdue = {"last_watered": old, "water_frequency_hours": 168}

    def is_overdue(p):
        if not p.get("last_watered"):
            return False
        watered = datetime.fromisoformat(p["last_watered"])
        if watered.tzinfo is None:
            watered = watered.replace(tzinfo=timezone.utc)
        hours = (now - watered).total_seconds() / 3600
        return hours > p.get("water_frequency_hours", 168)

    assert not is_overdue(plant_ok)
    assert is_overdue(plant_overdue)


def test_get_care_events_returns_list():
    """get_care_events should return a list from the API."""
    sample_event = {
        "id": 1,
        "plant_id": 1,
        "event_type": "watered",
        "detail": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plant_name": "Monstera",
    }

    with patch("plant_api.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [sample_event]

        events = plant_api.get_care_events(plant_id=1)
        assert len(events) == 1
        assert events[0]["event_type"] == "watered"


def test_get_care_events_backend_unreachable():
    """When the backend is down, get_care_events should return an empty list."""
    import requests as req

    with patch("plant_api.requests.get", side_effect=req.ConnectionError):
        events = plant_api.get_care_events()
        assert events == []


def test_create_care_event():
    """create_care_event should POST and return the created event."""
    created = {
        "id": 5,
        "plant_id": 1,
        "event_type": "note",
        "detail": "Repotted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plant_name": "Monstera",
    }

    with patch("plant_api.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = created
        mock_post.return_value.raise_for_status = lambda: None

        result = plant_api.create_care_event(
            {"plant_id": 1, "event_type": "note", "detail": "Repotted"}
        )
        assert result["id"] == 5
        assert result["detail"] == "Repotted"


def test_healthcheck_returns_true():
    """healthcheck should return True when backend responds 200."""
    with patch("plant_api.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert plant_api.healthcheck() is True


def test_healthcheck_returns_false_on_error():
    """healthcheck should return False when backend is unreachable."""
    import requests as req

    with patch("plant_api.requests.get", side_effect=req.ConnectionError):
        assert plant_api.healthcheck() is False
