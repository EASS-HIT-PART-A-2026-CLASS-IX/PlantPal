from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_advice_healthy_plant():
    payload = {
        "id": 1,
        "name": "Basil",
        "species": "Ocimum basilicum",
        "location": "Kitchen",
        "light_need": "high",
        "water_frequency_hours": 48,
        "health_status": "healthy",
        "notes": "smells great",
    }
    r = client.post("/advice", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["plant_id"] == 1
    assert data["plant_name"] == "Basil"
    assert len(data["tips"]) >= 3
    assert data["source"] in {"rule-based", "gemini"}


def test_advice_critical_plant_includes_urgent_tip():
    payload = {"name": "Sad Plant", "health_status": "critical"}
    r = client.post("/advice", json=payload)
    assert r.status_code == 200
    tips_text = " ".join(r.json()["tips"]).lower()
    assert "water" in tips_text
