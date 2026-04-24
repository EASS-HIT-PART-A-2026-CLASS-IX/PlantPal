"""HTTP client for the PlantPal backend.

The editor JWT is fetched once via ``ensure_token()`` and stored in
``st.session_state["_editor_token"]`` so it survives Streamlit reruns.
All write functions call ``ensure_token()`` first, then send the header.
Falls back gracefully when Streamlit is not the caller (tests, CLI).
"""

import os

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")

_USERNAME = os.getenv("DEFAULT_EDITOR_USERNAME", "gardener")
_PASSWORD = os.getenv("DEFAULT_EDITOR_PASSWORD", "plantpal")
_PREISSUED = os.getenv("EDITOR_TOKEN", "")


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def _st_session() -> dict | None:
    """Return st.session_state dict if running inside Streamlit, else None."""
    try:
        import streamlit as st
        # Accessing session_state raises if not in a Streamlit context
        _ = st.session_state
        return st.session_state
    except Exception:
        return None


def _fetch_token() -> str:
    """Call /token and return the JWT, or '' on any failure."""
    if _PREISSUED:
        return _PREISSUED
    try:
        resp = requests.post(
            f"{API_URL}/token",
            data={"username": _USERNAME, "password": _PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token", "")
    except Exception:
        pass
    return ""


def ensure_token() -> str:
    """Return a valid editor token, fetching one if needed.

    Stores the result in ``st.session_state`` so it persists across reruns.
    Falls back to a module-level variable when called outside Streamlit.
    """
    session = _st_session()
    if session is not None:
        token = session.get("_editor_token", "")
        if not token:
            token = _fetch_token()
            session["_editor_token"] = token
        return token
    else:
        # Outside Streamlit (tests / CLI)
        return _fetch_token()


def _auth(token: str | None = None) -> dict:
    t = token or ensure_token()
    return {"Authorization": f"Bearer {t}"} if t else {}


def _write(method, url, *, token: str | None = None, **kwargs) -> requests.Response:
    """Execute a write request, refreshing the token once on 401."""
    t = token or ensure_token()
    resp = method(url, headers=_auth(t), **kwargs)
    if resp.status_code == 401:
        # Force a fresh token and retry once
        session = _st_session()
        if session is not None:
            session["_editor_token"] = ""
        t = _fetch_token()
        if session is not None:
            session["_editor_token"] = t
        resp = method(url, headers=_auth(t), **kwargs)
    return resp


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_plants():
    try:
        resp = requests.get(f"{API_URL}/plants/")
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def create_plant(payload: dict):
    resp = _write(requests.post, f"{API_URL}/plants/", json=payload)
    resp.raise_for_status()
    return resp.json()


def update_plant(plant_id: int, payload: dict):
    resp = _write(requests.put, f"{API_URL}/plants/{plant_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


def patch_plant(plant_id: int, payload: dict):
    resp = _write(requests.patch, f"{API_URL}/plants/{plant_id}", json=payload)
    resp.raise_for_status()
    return resp.json()


def delete_plant(plant_id: int):
    resp = _write(requests.delete, f"{API_URL}/plants/{plant_id}")
    resp.raise_for_status()
    return True


def get_care_events(plant_id=None, event_type=None, limit=50):
    try:
        params: dict = {"limit": limit}
        if plant_id is not None:
            params["plant_id"] = plant_id
        if event_type is not None:
            params["event_type"] = event_type
        resp = requests.get(f"{API_URL}/care-events/", params=params)
        return resp.json() if resp.status_code == 200 else []
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
