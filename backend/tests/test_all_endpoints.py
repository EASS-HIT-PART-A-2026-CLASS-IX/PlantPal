"""Comprehensive endpoint tests — hits every API route and validates
status codes, response shapes, and core behaviour in a single file.

Run with:  uv run pytest tests/test_all_endpoints.py -v

Classes
-------
TestHealth            GET /health               (2 tests)
TestDocs              GET /docs, /openapi.json   (2 tests)
TestCreatePlant       POST /plants/              (5 tests)
TestListPlants        GET /plants/               (5 tests)
TestGetPlant          GET /plants/{id}           (2 tests)
TestUpdatePlant       PUT /plants/{id}           (4 tests)
TestPatchPlant        PATCH /plants/{id}         (7 tests)
TestDeletePlant       DELETE /plants/{id}        (3 tests)
TestListCareEvents    GET /care-events/          (6 tests)
TestCreateCareEvent   POST /care-events/         (6 tests)
TestHealthDegradation cross-cutting behaviour    (4 tests)
TestFullLifecycle     end-to-end integration     (1 test)
TestRootPath          GET / returns 404          (1 test)
"""

from datetime import datetime, timedelta, timezone

import pytest

PLANT_PAYLOAD = {
    "name": "Snake Plant",
    "species": "Dracaena trifasciata",
    "location": "Office",
    "light_need": "low",
    "water_frequency_hours": 336,
    "health_status": "healthy",
    "notes": "Very forgiving",
}

PLANT_FIELDS = {
    "id", "name", "species", "location", "light_need",
    "water_frequency_hours", "last_watered", "health_status",
    "image_url", "notes",
}

CARE_EVENT_FIELDS = {
    "id", "plant_id", "event_type", "detail", "created_at", "plant_name",
}


# ── GET /health ──────────────────────────────────────────────────────

class TestHealth:
    """GET /health — verify the health check endpoint returns the expected JSON."""

    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_body_shape(self, client):
        data = client.get("/health").json()
        assert data == {"status": "ok", "service": "plantpal-backend"}


# ── GET /docs & /openapi.json ───────────────────────────────────────

class TestDocs:
    """GET /docs and /openapi.json — verify Swagger UI and OpenAPI spec are served."""

    def test_swagger_ui(self, client):
        assert client.get("/docs").status_code == 200

    def test_openapi_spec(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "paths" in spec
        expected_paths = [
            "/health", "/plants/", "/plants/{plant_id}",
            "/care-events/",
        ]
        for p in expected_paths:
            assert p in spec["paths"], f"Missing path {p} in OpenAPI spec"


# ── POST /plants/ ───────────────────────────────────────────────────

class TestCreatePlant:
    """POST /plants/ — create a plant and validate response shape and defaults."""

    def test_returns_200_with_all_fields(self, client):
        resp = client.post("/plants/", json=PLANT_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert PLANT_FIELDS.issubset(data.keys())
        assert data["name"] == "Snake Plant"
        assert isinstance(data["id"], int)

    def test_auto_fills_last_watered(self, client):
        resp = client.post("/plants/", json=PLANT_PAYLOAD)
        assert resp.json()["last_watered"] is not None

    def test_auto_fills_image_url(self, client):
        resp = client.post("/plants/", json=PLANT_PAYLOAD)
        assert resp.json()["image_url"] != ""

    def test_422_on_missing_required_fields(self, client):
        assert client.post("/plants/", json={"name": "Oops"}).status_code == 422

    def test_422_on_wrong_type(self, client):
        bad = {**PLANT_PAYLOAD, "water_frequency_hours": "weekly"}
        assert client.post("/plants/", json=bad).status_code == 422


# ── GET /plants/ ────────────────────────────────────────────────────

class TestListPlants:
    """GET /plants/ — list plants with pagination (skip/limit) support."""

    def test_empty_initially(self, client):
        resp = client.get("/plants/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_created_plants(self, client):
        client.post("/plants/", json=PLANT_PAYLOAD)
        client.post("/plants/", json={**PLANT_PAYLOAD, "name": "Fern", "species": "Nephrolepis"})
        plants = client.get("/plants/").json()
        assert len(plants) == 2
        assert all(PLANT_FIELDS.issubset(p.keys()) for p in plants)

    def test_persisted_names_match(self, client):
        client.post("/plants/", json=PLANT_PAYLOAD)
        client.post("/plants/", json={**PLANT_PAYLOAD, "name": "Pothos", "species": "Epipremnum aureum"})
        names = {p["name"] for p in client.get("/plants/").json()}
        assert names == {"Snake Plant", "Pothos"}

    def test_skip_param(self, client):
        for i in range(3):
            client.post("/plants/", json={**PLANT_PAYLOAD, "name": f"P{i}", "species": f"S{i}"})
        assert len(client.get("/plants/", params={"skip": 2}).json()) == 1

    def test_limit_param(self, client):
        for i in range(3):
            client.post("/plants/", json={**PLANT_PAYLOAD, "name": f"P{i}", "species": f"S{i}"})
        assert len(client.get("/plants/", params={"limit": 1}).json()) == 1


# ── GET /plants/{id} ───────────────────────────────────────────────

class TestGetPlant:
    """GET /plants/{id} — fetch a single plant by ID, 404 on missing."""

    def test_returns_correct_plant(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        resp = client.get(f"/plants/{pid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == pid
        assert resp.json()["name"] == "Snake Plant"

    def test_404_for_nonexistent(self, client):
        assert client.get("/plants/999").status_code == 404


# ── PUT /plants/{id} ───────────────────────────────────────────────

class TestUpdatePlant:
    """PUT /plants/{id} — full update, edit event logging, 404 on missing."""

    def test_replaces_all_fields(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        updated = {**PLANT_PAYLOAD, "name": "Updated Snake", "location": "Balcony"}
        resp = client.put(f"/plants/{pid}", json=updated)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Snake"
        assert data["location"] == "Balcony"

    def test_logs_edited_events(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.put(f"/plants/{pid}", json={**PLANT_PAYLOAD, "location": "Roof"})
        events = client.get("/care-events/", params={"plant_id": pid}).json()
        edits = [e for e in events if e["event_type"] == "edited"]
        assert any("location" in e["detail"] for e in edits)

    def test_logs_multiple_field_changes(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.put(
            f"/plants/{pid}",
            json={**PLANT_PAYLOAD, "location": "Bedroom", "light_need": "high"},
        )
        events = client.get("/care-events/", params={"plant_id": pid}).json()
        details = {e["detail"] for e in events if e["event_type"] == "edited"}
        assert "location: Office -> Bedroom" in details
        assert "light need: low -> high" in details

    def test_404_for_nonexistent(self, client):
        assert client.put("/plants/999", json=PLANT_PAYLOAD).status_code == 404


# ── PATCH /plants/{id} ─────────────────────────────────────────────

class TestPatchPlant:
    """PATCH /plants/{id} — partial update, watering auto-heal, event logging."""

    def test_partial_update(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        resp = client.patch(f"/plants/{pid}", json={"notes": "New note"})
        assert resp.status_code == 200
        assert resp.json()["notes"] == "New note"
        assert resp.json()["name"] == "Snake Plant"  # unchanged fields stay

    def test_watering_resets_unhealthy_to_healthy(self, client):
        pid = client.post(
            "/plants/", json={**PLANT_PAYLOAD, "health_status": "needs_attention"}
        ).json()["id"]
        resp = client.patch(
            f"/plants/{pid}",
            json={"last_watered": datetime.now(timezone.utc).isoformat()},
        )
        assert resp.json()["health_status"] == "healthy"

    def test_watering_respects_explicit_health_override(self, client):
        pid = client.post(
            "/plants/", json={**PLANT_PAYLOAD, "health_status": "critical"}
        ).json()["id"]
        resp = client.patch(
            f"/plants/{pid}",
            json={
                "last_watered": datetime.now(timezone.utc).isoformat(),
                "health_status": "needs_attention",
            },
        )
        assert resp.json()["health_status"] == "needs_attention"

    def test_watering_logs_care_event(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.patch(
            f"/plants/{pid}",
            json={"last_watered": datetime.now(timezone.utc).isoformat()},
        )
        events = client.get("/care-events/", params={"plant_id": pid}).json()
        assert any(e["event_type"] == "watered" for e in events)

    def test_unchanged_field_no_event(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.patch(f"/plants/{pid}", json={"location": "Office"})
        events = client.get("/care-events/", params={"plant_id": pid}).json()
        assert not any(e["event_type"] == "edited" for e in events)

    def test_logs_edited_events(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.patch(f"/plants/{pid}", json={"notes": "Repotted today"})
        events = client.get("/care-events/", params={"plant_id": pid}).json()
        edits = [e for e in events if e["event_type"] == "edited"]
        assert len(edits) == 1
        assert "notes" in edits[0]["detail"]

    def test_404_for_nonexistent(self, client):
        assert client.patch("/plants/999", json={"notes": "x"}).status_code == 404


# ── DELETE /plants/{id} ─────────────────────────────────────────────

class TestDeletePlant:
    """DELETE /plants/{id} — remove a plant, verify gone from list and GET."""

    def test_deletes_plant(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        resp = client.delete(f"/plants/{pid}")
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Plant deleted successfully"
        assert client.get(f"/plants/{pid}").status_code == 404

    def test_gone_from_list(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.delete(f"/plants/{pid}")
        assert client.get("/plants/").json() == []

    def test_404_for_nonexistent(self, client):
        assert client.delete("/plants/999").status_code == 404


# ── GET /care-events/ ──────────────────────────────────────────────

class TestListCareEvents:
    """GET /care-events/ — list events with plant_id, event_type, and limit filters."""

    def test_empty_initially(self, client):
        resp = client.get("/care-events/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_created_events(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.post("/care-events/", json={"plant_id": pid, "event_type": "note", "detail": "a"})
        client.post("/care-events/", json={"plant_id": pid, "event_type": "note", "detail": "b"})
        events = client.get("/care-events/").json()
        assert len(events) == 2
        assert all(CARE_EVENT_FIELDS.issubset(e.keys()) for e in events)

    def test_filter_by_plant_id(self, client):
        pid1 = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        pid2 = client.post(
            "/plants/", json={**PLANT_PAYLOAD, "name": "Cactus", "species": "Cactaceae"}
        ).json()["id"]
        client.post("/care-events/", json={"plant_id": pid1, "detail": "x"})
        client.post("/care-events/", json={"plant_id": pid2, "detail": "y"})

        events = client.get("/care-events/", params={"plant_id": pid1}).json()
        assert len(events) == 1
        assert events[0]["plant_id"] == pid1

    def test_filter_by_event_type(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.post("/care-events/", json={"plant_id": pid, "event_type": "note", "detail": "a"})
        client.patch(
            f"/plants/{pid}",
            json={"last_watered": datetime.now(timezone.utc).isoformat()},
        )
        notes = client.get("/care-events/", params={"event_type": "note"}).json()
        watered = client.get("/care-events/", params={"event_type": "watered"}).json()
        assert all(e["event_type"] == "note" for e in notes)
        assert all(e["event_type"] == "watered" for e in watered)

    def test_limit_param(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        for i in range(5):
            client.post("/care-events/", json={"plant_id": pid, "detail": str(i)})
        assert len(client.get("/care-events/", params={"limit": 2}).json()) == 2

    def test_combined_filters(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.post("/care-events/", json={"plant_id": pid, "event_type": "note", "detail": "a"})
        client.post("/care-events/", json={"plant_id": pid, "event_type": "note", "detail": "b"})
        client.patch(
            f"/plants/{pid}",
            json={"last_watered": datetime.now(timezone.utc).isoformat()},
        )
        events = client.get(
            "/care-events/", params={"plant_id": pid, "event_type": "note"}
        ).json()
        assert len(events) == 2
        assert all(e["event_type"] == "note" for e in events)


# ── POST /care-events/ ─────────────────────────────────────────────

class TestCreateCareEvent:
    """POST /care-events/ — create events, validate response fields and errors."""

    def test_creates_event_with_all_fields(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        resp = client.post(
            "/care-events/",
            json={"plant_id": pid, "event_type": "note", "detail": "Pruned leaves"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert CARE_EVENT_FIELDS.issubset(data.keys())
        assert data["event_type"] == "note"
        assert data["detail"] == "Pruned leaves"
        assert data["plant_name"] == "Snake Plant"
        assert isinstance(data["id"], int)
        assert data["created_at"] != ""

    def test_created_event_appears_in_list(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        client.post(
            "/care-events/",
            json={"plant_id": pid, "event_type": "note", "detail": "Repotted"},
        )
        events = client.get("/care-events/").json()
        assert len(events) == 1
        assert events[0]["detail"] == "Repotted"

    def test_auto_fills_created_at(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        data = client.post(
            "/care-events/", json={"plant_id": pid, "detail": "x"}
        ).json()
        assert data["created_at"] != ""

    def test_custom_created_at(self, client):
        pid = client.post("/plants/", json=PLANT_PAYLOAD).json()["id"]
        ts = "2026-01-01T00:00:00+00:00"
        data = client.post(
            "/care-events/",
            json={"plant_id": pid, "detail": "x", "created_at": ts},
        ).json()
        assert data["created_at"] == ts

    def test_422_missing_plant_id(self, client):
        resp = client.post(
            "/care-events/", json={"event_type": "note", "detail": "x"}
        )
        assert resp.status_code == 422

    def test_404_nonexistent_plant(self, client):
        resp = client.post(
            "/care-events/",
            json={"plant_id": 9999, "event_type": "note", "detail": "ghost"},
        )
        assert resp.status_code == 404


# ── Health degradation (cross-cutting) ──────────────────────────────

class TestHealthDegradation:
    """Cross-cutting — auto-degradation of health when a plant is overdue for watering."""

    def _overdue_plant(self, client, hours_ago: int):
        past = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
        return client.post(
            "/plants/",
            json={**PLANT_PAYLOAD, "last_watered": past, "water_frequency_hours": 168},
        ).json()["id"]

    def test_overdue_becomes_needs_attention(self, client):
        pid = self._overdue_plant(client, hours_ago=180)
        data = client.get(f"/plants/{pid}").json()
        assert data["health_status"] == "needs_attention"

    def test_very_overdue_becomes_critical(self, client):
        pid = self._overdue_plant(client, hours_ago=300)
        data = client.get(f"/plants/{pid}").json()
        assert data["health_status"] == "critical"

    def test_degradation_logs_health_changed_event(self, client):
        pid = self._overdue_plant(client, hours_ago=300)
        client.get(f"/plants/{pid}")
        events = client.get("/care-events/", params={"plant_id": pid}).json()
        health_events = [e for e in events if e["event_type"] == "health_changed"]
        assert len(health_events) >= 1
        assert "critical" in health_events[0]["detail"]

    def test_on_time_stays_healthy(self, client):
        now = datetime.now(timezone.utc).isoformat()
        pid = client.post(
            "/plants/",
            json={**PLANT_PAYLOAD, "last_watered": now, "water_frequency_hours": 168},
        ).json()["id"]
        assert client.get(f"/plants/{pid}").json()["health_status"] == "healthy"


# ── Full CRUD lifecycle (integration) ───────────────────────────────

class TestFullLifecycle:
    """End-to-end integration — walk a plant through create, read, update, patch, and delete."""

    def test_create_read_update_patch_delete(self, client):
        """Walk through the complete lifecycle of a plant and its events."""
        created = client.post("/plants/", json=PLANT_PAYLOAD).json()
        pid = created["id"]
        assert created["name"] == "Snake Plant"

        fetched = client.get(f"/plants/{pid}").json()
        assert fetched["id"] == pid

        put_resp = client.put(
            f"/plants/{pid}", json={**PLANT_PAYLOAD, "name": "Renamed"}
        ).json()
        assert put_resp["name"] == "Renamed"

        patch_resp = client.patch(
            f"/plants/{pid}",
            json={"last_watered": datetime.now(timezone.utc).isoformat()},
        ).json()
        assert patch_resp["health_status"] == "healthy"

        client.post(
            "/care-events/",
            json={"plant_id": pid, "event_type": "note", "detail": "Looking great"},
        )

        events = client.get("/care-events/", params={"plant_id": pid}).json()
        types = {e["event_type"] for e in events}
        assert "edited" in types
        assert "watered" in types
        assert "note" in types

        client.delete(f"/plants/{pid}")
        assert client.get(f"/plants/{pid}").status_code == 404


# ── Root path (no route at /) ───────────────────────────────────────

class TestRootPath:
    """GET / — confirm no route is defined at the root path."""

    def test_root_returns_404(self, client):
        assert client.get("/").status_code == 404
