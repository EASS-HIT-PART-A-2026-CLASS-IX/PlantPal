SAMPLE = {
    "name": "Monstera",
    "species": "Monstera deliciosa",
    "location": "Living Room",
    "light_need": "medium",
    "water_frequency_days": 7,
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


def test_delete_plant_not_found(client):
    resp = client.delete("/plants/999")
    assert resp.status_code == 404


def test_create_plant_missing_field(client):
    resp = client.post("/plants/", json={"name": "Fern"})
    assert resp.status_code == 422


def test_create_plant_invalid_type(client):
    resp = client.post("/plants/", json={**SAMPLE, "water_frequency_days": "weekly"})
    assert resp.status_code == 422


def test_watering_resets_health_to_healthy(client):
    plant_id = client.post(
        "/plants/", json={**SAMPLE, "health_status": "needs_attention"}
    ).json()["id"]
    resp = client.patch(f"/plants/{plant_id}", json={"last_watered": "2026-04-12"})
    assert resp.status_code == 200
    assert resp.json()["health_status"] == "healthy"


def test_watering_keeps_explicit_health_override(client):
    plant_id = client.post(
        "/plants/", json={**SAMPLE, "health_status": "critical"}
    ).json()["id"]
    resp = client.patch(
        f"/plants/{plant_id}",
        json={"last_watered": "2026-04-12", "health_status": "needs_attention"},
    )
    assert resp.status_code == 200
    assert resp.json()["health_status"] == "needs_attention"


def test_create_then_list_persistence(client):
    client.post("/plants/", json=SAMPLE)
    client.post("/plants/", json={**SAMPLE, "name": "Pothos", "species": "Epipremnum aureum"})
    plants = client.get("/plants/").json()
    assert len(plants) == 2
    names = {p["name"] for p in plants}
    assert names == {"Monstera", "Pothos"}
