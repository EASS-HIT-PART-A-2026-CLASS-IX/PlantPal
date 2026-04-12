SAMPLE = {
    "name": "Monstera",
    "species": "Monstera deliciosa",
    "location": "Living Room",
    "light_need": "medium",
    "water_frequency_hours": 168,
    "health_status": "healthy",
    "notes": "Loves humidity",
}


def test_create_plant(client):
    resp = client.post("/plants/", json=SAMPLE)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Monstera"
    assert data["id"] is not None
    assert data["last_watered"] is not None


def test_list_plants(client):
    client.post("/plants/", json=SAMPLE)
    resp = client.get("/plants/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_plant(client):
    plant_id = client.post("/plants/", json=SAMPLE).json()["id"]
    resp = client.get(f"/plants/{plant_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Monstera"


def test_update_plant_put(client):
    plant_id = client.post("/plants/", json=SAMPLE).json()["id"]
    updated = {**SAMPLE, "name": "Big Monstera", "location": "Bedroom"}
    resp = client.put(f"/plants/{plant_id}", json=updated)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Big Monstera"
    assert resp.json()["location"] == "Bedroom"


def test_patch_plant(client):
    plant_id = client.post("/plants/", json=SAMPLE).json()["id"]
    resp = client.patch(f"/plants/{plant_id}", json={"health_status": "critical"})
    assert resp.status_code == 200
    assert resp.json()["health_status"] == "critical"
    assert resp.json()["name"] == "Monstera"


def test_delete_plant(client):
    plant_id = client.post("/plants/", json=SAMPLE).json()["id"]
    resp = client.delete(f"/plants/{plant_id}")
    assert resp.status_code == 200
    assert client.get("/plants/").json() == []


def test_get_plant_not_found(client):
    resp = client.get("/plants/999")
    assert resp.status_code == 404


def test_update_plant_not_found(client):
    resp = client.put("/plants/999", json=SAMPLE)
    assert resp.status_code == 404


def test_patch_plant_not_found(client):
    resp = client.patch("/plants/999", json={"notes": "gone"})
    assert resp.status_code == 404


def test_delete_plant_not_found(client):
    resp = client.delete("/plants/999")
    assert resp.status_code == 404


def test_create_plant_missing_field(client):
    resp = client.post("/plants/", json={"name": "Fern"})
    assert resp.status_code == 422


def test_create_plant_invalid_type(client):
    resp = client.post("/plants/", json={**SAMPLE, "water_frequency_hours": "weekly"})
    assert resp.status_code == 422


def test_watering_resets_health_to_healthy(client):
    plant_id = client.post(
        "/plants/", json={**SAMPLE, "health_status": "needs_attention"}
    ).json()["id"]
    resp = client.patch(
        f"/plants/{plant_id}",
        json={"last_watered": "2026-04-12T10:00:00+00:00"},
    )
    assert resp.status_code == 200
    assert resp.json()["health_status"] == "healthy"


def test_watering_keeps_explicit_health_override(client):
    plant_id = client.post(
        "/plants/", json={**SAMPLE, "health_status": "critical"}
    ).json()["id"]
    resp = client.patch(
        f"/plants/{plant_id}",
        json={
            "last_watered": "2026-04-12T10:00:00+00:00",
            "health_status": "needs_attention",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["health_status"] == "needs_attention"


def test_overdue_degrades_to_needs_attention(client):
    """A plant overdue by less than 50% of its frequency becomes needs_attention."""
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(hours=180)).isoformat()
    plant_id = client.post(
        "/plants/",
        json={**SAMPLE, "last_watered": past, "water_frequency_hours": 168},
    ).json()["id"]
    resp = client.get(f"/plants/{plant_id}")
    assert resp.status_code == 200
    assert resp.json()["health_status"] == "needs_attention"


def test_overdue_degrades_to_critical(client):
    """A plant overdue by more than 50% of its frequency becomes critical."""
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(hours=300)).isoformat()
    plant_id = client.post(
        "/plants/",
        json={**SAMPLE, "last_watered": past, "water_frequency_hours": 168},
    ).json()["id"]
    resp = client.get(f"/plants/{plant_id}")
    assert resp.status_code == 200
    assert resp.json()["health_status"] == "critical"


def test_list_plants_pagination(client):
    """skip and limit query params control which plants are returned."""
    client.post("/plants/", json=SAMPLE)
    client.post("/plants/", json={**SAMPLE, "name": "Pothos", "species": "Epipremnum aureum"})
    client.post("/plants/", json={**SAMPLE, "name": "Fern", "species": "Nephrolepis"})

    all_plants = client.get("/plants/").json()
    assert len(all_plants) == 3

    limited = client.get("/plants/", params={"limit": 2}).json()
    assert len(limited) == 2

    skipped = client.get("/plants/", params={"skip": 2}).json()
    assert len(skipped) == 1


def test_create_then_list_persistence(client):
    client.post("/plants/", json=SAMPLE)
    client.post("/plants/", json={**SAMPLE, "name": "Pothos", "species": "Epipremnum aureum"})
    plants = client.get("/plants/").json()
    assert len(plants) == 2
    names = {p["name"] for p in plants}
    assert names == {"Monstera", "Pothos"}


def test_watering_logs_care_event(client):
    """PATCHing last_watered should auto-create a 'watered' CareEvent."""
    plant_id = client.post("/plants/", json=SAMPLE).json()["id"]
    client.patch(
        f"/plants/{plant_id}",
        json={"last_watered": "2026-04-12T12:00:00+00:00"},
    )
    events = client.get("/care-events/", params={"plant_id": plant_id}).json()
    watered = [e for e in events if e["event_type"] == "watered"]
    assert len(watered) == 1
    assert watered[0]["plant_id"] == plant_id


def test_health_degradation_logs_care_event(client):
    """Reading an overdue plant should auto-create a 'health_changed' CareEvent."""
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(hours=300)).isoformat()
    plant_id = client.post(
        "/plants/",
        json={**SAMPLE, "last_watered": past, "water_frequency_hours": 168},
    ).json()["id"]
    client.get(f"/plants/{plant_id}")
    events = client.get("/care-events/", params={"plant_id": plant_id}).json()
    health_events = [e for e in events if e["event_type"] == "health_changed"]
    assert len(health_events) >= 1
    assert "critical" in health_events[0]["detail"]
