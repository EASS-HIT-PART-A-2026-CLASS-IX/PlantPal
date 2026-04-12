import os

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")


def get_plants():
    try:
        resp = requests.get(f"{API_URL}/plants/")
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


def create_plant(payload: dict):
    resp = requests.post(f"{API_URL}/plants/", json=payload)
    resp.raise_for_status()
    return resp.json()


def update_plant(plant_id: int, payload: dict):
    resp = requests.put(f"{API_URL}/plants/{plant_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


def patch_plant(plant_id: int, payload: dict):
    resp = requests.patch(f"{API_URL}/plants/{plant_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


def delete_plant(plant_id: int):
    resp = requests.delete(f"{API_URL}/plants/{plant_id}")
    resp.raise_for_status()
    return True


def get_care_events(plant_id=None, event_type=None, limit=50):
    try:
        params = {"limit": limit}
        if plant_id is not None:
            params["plant_id"] = plant_id
        if event_type is not None:
            params["event_type"] = event_type
        resp = requests.get(f"{API_URL}/care-events/", params=params)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


def create_care_event(payload: dict):
    resp = requests.post(f"{API_URL}/care-events/", json=payload)
    resp.raise_for_status()
    return resp.json()


def healthcheck():
    try:
        resp = requests.get(f"{API_URL}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False
