SAMPLE_PLANT = {
    "name": "Monstera",
    "species": "Monstera deliciosa",
    "location": "Living Room",
    "light_need": "medium",
    "water_frequency_hours": 168,
    "health_status": "healthy",
    "notes": "Loves humidity",
}

SAMPLE_PLANT_2 = {
    "name": "Pothos",
    "species": "Epipremnum aureum",
    "location": "Bedroom",
    "light_need": "low",
    "water_frequency_hours": 120,
    "health_status": "healthy",
    "notes": "",
}


def test_list_care_events_empty(client):
    resp = client.get("/care-events/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_care_event_note(client):
    plant_id = client.post("/plants/", json=SAMPLE_PLANT).json()["id"]
    resp = client.post(
        "/care-events/",
        json={"plant_id": plant_id, "event_type": "note", "detail": "Repotted"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_type"] == "note"
    assert data["detail"] == "Repotted"
    assert data["plant_name"] == "Monstera"

    events = client.get("/care-events/").json()
    assert len(events) == 1


def test_filter_by_plant_id(client):
    pid1 = client.post("/plants/", json=SAMPLE_PLANT).json()["id"]
    pid2 = client.post("/plants/", json=SAMPLE_PLANT_2).json()["id"]
    client.post("/care-events/", json={"plant_id": pid1, "detail": "note1"})
    client.post("/care-events/", json={"plant_id": pid2, "detail": "note2"})

    resp = client.get("/care-events/", params={"plant_id": pid1})
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["plant_id"] == pid1


def test_filter_by_event_type(client):
    pid = client.post("/plants/", json=SAMPLE_PLANT).json()["id"]
    client.post("/care-events/", json={"plant_id": pid, "event_type": "note", "detail": "a"})
    client.patch(f"/plants/{pid}", json={"last_watered": "2026-04-12T10:00:00+00:00"})

    notes = client.get("/care-events/", params={"event_type": "note"}).json()
    watered = client.get("/care-events/", params={"event_type": "watered"}).json()
    assert len(notes) == 1
    assert len(watered) == 1
    assert notes[0]["event_type"] == "note"
    assert watered[0]["event_type"] == "watered"


def test_create_care_event_response_fields(client):
    """POST response includes id, created_at, and plant_name."""
    plant_id = client.post("/plants/", json=SAMPLE_PLANT).json()["id"]
    resp = client.post(
        "/care-events/",
        json={"plant_id": plant_id, "event_type": "note", "detail": "Pruned"},
    )
    data = resp.json()
    assert "id" in data and isinstance(data["id"], int)
    assert data["created_at"] != ""
    assert data["plant_name"] == "Monstera"
    assert data["plant_id"] == plant_id


def test_list_care_events_limit(client):
    """The limit query param caps the number of returned events."""
    pid = client.post("/plants/", json=SAMPLE_PLANT).json()["id"]
    for i in range(5):
        client.post("/care-events/", json={"plant_id": pid, "detail": f"n{i}"})

    all_events = client.get("/care-events/").json()
    assert len(all_events) == 5

    limited = client.get("/care-events/", params={"limit": 2}).json()
    assert len(limited) == 2


def test_create_care_event_missing_plant_id(client):
    """POST without plant_id should return 422."""
    resp = client.post("/care-events/", json={"event_type": "note", "detail": "oops"})
    assert resp.status_code == 422


def test_care_event_not_found_plant(client):
    resp = client.post(
        "/care-events/",
        json={"plant_id": 9999, "event_type": "note", "detail": "ghost"},
    )
    assert resp.status_code == 404
