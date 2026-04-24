import json
import math
import os
from datetime import datetime, timezone

import requests
import streamlit as st

import plant_api
import cached_api

API_URL = os.getenv("API_URL", "http://localhost:8000")


def get_advice(plant_id: int) -> dict | None:
    try:
        resp = requests.get(f"{API_URL}/plants/{plant_id}/advice", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PlantPal",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css():
    import os

    css_path = os.path.join(os.path.dirname(__file__), "theme.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css()

# Ensure we have an editor token before any button is pressed.
# Stores result in st.session_state so it survives across reruns.
plant_api.ensure_token()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
LIGHT_ICONS = {"low": "🌑", "medium": "🌤️", "high": "☀️"}
HEALTH_CSS = {
    "healthy": ("healthy", "Healthy"),
    "needs_attention": ("attention", "Needs Attention"),
    "critical": ("critical", "Critical"),
}

CIRCUMFERENCE = 2 * math.pi * 34  # ~213.6 for r=34


def hours_since_watered(last_watered: str | None) -> float | None:
    """Return hours elapsed since the ISO-8601 ``last_watered`` timestamp,
    or None if the value is missing or unparseable.  Naive datetimes are
    treated as UTC."""
    if not last_watered:
        return None
    try:
        watered = datetime.fromisoformat(last_watered)
        if watered.tzinfo is None:
            watered = watered.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - watered
        return delta.total_seconds() / 3600
    except ValueError:
        return None


def is_overdue(plant: dict) -> bool:
    """True when more hours have passed since the last watering than the
    plant's ``water_frequency_hours`` schedule allows."""
    hours = hours_since_watered(plant.get("last_watered"))
    if hours is None:
        return False
    return hours > plant.get("water_frequency_hours", 168)


def format_relative(last_watered: str | None) -> str:
    hours = hours_since_watered(last_watered)
    if hours is None:
        return "Never"
    if hours < 1:
        return f"{int(hours * 60)} min ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    days = int(hours / 24)
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


def format_frequency(hours: int) -> str:
    if hours < 24:
        return f"Every {hours}h"
    days = hours / 24
    if days == int(days):
        return f"Every {int(days)} days"
    return f"Every {days:.1f} days"


def watering_ring_html(plant: dict) -> str:
    """Build an SVG watering-ring showing elapsed vs scheduled time."""
    hours = hours_since_watered(plant.get("last_watered"))
    freq = plant.get("water_frequency_hours", 168)

    if hours is None:
        pct = 0.0
        time_text = "Never watered"
        sub_text = f"Schedule: {format_frequency(freq)}"
        ring_class = ""
    else:
        pct = min(hours / freq, 1.0) if freq > 0 else 1.0
        time_text = format_relative(plant.get("last_watered"))
        remaining = freq - hours
        if remaining > 0:
            if remaining < 24:
                sub_text = f"Next in {int(remaining)}h"
            else:
                sub_text = f"Next in {int(remaining / 24)}d"
        else:
            sub_text = "Overdue!"
        if pct >= 1.0:
            ring_class = "overdue"
        elif pct >= 0.75:
            ring_class = "warn"
        else:
            ring_class = ""

    offset = CIRCUMFERENCE * (1 - pct)

    return f"""<div class="watering-section">
  <svg class="water-ring" viewBox="0 0 80 80">
    <circle class="ring-bg" cx="40" cy="40" r="34"/>
    <circle class="ring-fill {ring_class}" cx="40" cy="40" r="34"
            stroke-dasharray="{CIRCUMFERENCE:.1f}"
            stroke-dashoffset="{offset:.1f}"/>
  </svg>
  <div class="water-label">
    <div class="water-time">{time_text}</div>
    <div class="water-sub">{sub_text}</div>
  </div>
</div>"""


def plant_card_html(plant: dict) -> str:
    """Return the custom HTML for a single plant card."""
    overdue = is_overdue(plant)
    css_class, health_label = HEALTH_CSS.get(
        plant["health_status"], ("", plant["health_status"])
    )
    light_icon = LIGHT_ICONS.get(plant["light_need"], "")
    freq_hours = plant.get("water_frequency_hours", 168)

    name_html = plant["name"]
    if overdue:
        name_html += ' <span class="overdue-dot"></span>'

    notes_html = ""
    if plant.get("notes"):
        escaped = plant["notes"][:80].replace("&", "&amp;").replace("<", "&lt;")
        notes_html = f'<div class="card-notes">{escaped}</div>'

    ring = watering_ring_html(plant)

    return f"""<div class="plant-card">
  <div class="card-header">
    <div>
      <div class="card-name">{name_html}</div>
      <div class="card-species">{plant["species"]}</div>
    </div>
    <span class="health-pill {css_class}">{health_label}</span>
  </div>
  <div class="card-info">
    <div class="info-row"><span class="info-icon">📍</span><span>{plant["location"]}</span></div>
    <div class="info-row"><span class="info-icon">{light_icon}</span><span>{plant["light_need"].capitalize()} light</span></div>
    <div class="info-row"><span class="info-icon">🔄</span><span>{format_frequency(freq_hours)}</span></div>
  </div>
  {ring}
  {notes_html}
</div>"""


# ---------------------------------------------------------------------------
# Sidebar — navigation + search/filters
# ---------------------------------------------------------------------------
all_plants = cached_api.get_plants()

with st.sidebar:
    st.markdown("## 🌿 PlantPal")
    st.caption("Indoor Plant Care Tracker")
    st.divider()

    page = st.radio(
        "Navigate",
        ["Dashboard", "Care Log"],
        label_visibility="collapsed",
    )

    st.divider()

    # Search & filter controls (only visible on Dashboard)
    if page == "Dashboard":
        search = st.text_input("🔍 Search", placeholder="Search by name…", label_visibility="collapsed")

        with st.expander("Filters", expanded=False):
            locations = sorted({p["location"] for p in all_plants})
            filter_loc = st.multiselect("Location", locations, placeholder="All locations")
            filter_health = st.multiselect(
                "Health", ["healthy", "needs_attention", "critical"], placeholder="All"
            )
            filter_light = st.multiselect("Light", ["low", "medium", "high"], placeholder="All")

        st.divider()

    backend_ok = plant_api.healthcheck()
    if backend_ok:
        st.success("Backend connected", icon="✅")
    else:
        st.error("Backend unreachable", icon="🚫")

    st.divider()
    st.markdown(
        "<div style='text-align:center; font-size:0.75rem; opacity:0.6;'>"
        "&copy; 2026 Roy Carter. All rights reserved."
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Care Log page (delegated)
# ---------------------------------------------------------------------------
if page == "Care Log":
    st.session_state["_prev_page"] = "Care Log"
    import care_log

    care_log.render()
    st.stop()

# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

if st.session_state.get("_prev_page") != "Dashboard":
    for key in list(st.session_state):
        if key.startswith(("editing_", "confirm_del_")):
            del st.session_state[key]
    st.session_state.pop("show_add_form", None)
st.session_state["_prev_page"] = "Dashboard"

plants = all_plants

# -- Compute metrics --
total = len(plants)
healthy = sum(1 for p in plants if p.get("health_status") == "healthy")
overdue_count = sum(1 for p in plants if is_overdue(p))
critical_count = sum(1 for p in plants if p.get("health_status") == "critical")

# -- Welcome Banner --
if overdue_count > 0:
    status_html = f'<span class="water-alert">{overdue_count} need{"s" if overdue_count == 1 else ""} water</span>'
else:
    status_html = '<span class="all-good">All plants are on track!</span>'

st.markdown(
    f"""<div class="welcome-banner">
  <div>
    <div class="welcome-greeting">Welcome back, Plant Parent</div>
    <div class="welcome-subtitle">
      You have <strong>{total}</strong> plant{"s" if total != 1 else ""} in your garden &mdash; {status_html}
    </div>
  </div>
  <div class="welcome-icon">🌿</div>
</div>""",
    unsafe_allow_html=True,
)

if st.button("➕ Add Plant", use_container_width=True, type="primary"):
    st.session_state["show_add_form"] = True

# -- Stats Strip --
st.markdown(
    f"""<div class="stats-strip">
  <div class="stat-item">
    <div class="stat-emoji">🌱</div>
    <div class="stat-number">{total}</div>
    <div class="stat-label">Total Plants</div>
  </div>
  <div class="stat-separator"></div>
  <div class="stat-item">
    <div class="stat-emoji">💚</div>
    <div class="stat-number healthy-color">{healthy}</div>
    <div class="stat-label">Healthy</div>
  </div>
  <div class="stat-separator"></div>
  <div class="stat-item">
    <div class="stat-emoji">💧</div>
    <div class="stat-number water-color">{overdue_count}</div>
    <div class="stat-label">Need Water</div>
  </div>
  <div class="stat-separator"></div>
  <div class="stat-item">
    <div class="stat-emoji">⚠️</div>
    <div class="stat-number danger-color">{critical_count}</div>
    <div class="stat-label">Critical</div>
  </div>
</div>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Add Plant dialog
# ---------------------------------------------------------------------------
if st.session_state.get("show_add_form"):

    @st.dialog("Add a New Plant")
    def add_dialog():
        name = st.text_input("Name *")
        species = st.text_input("Species *")
        location = st.selectbox(
            "Location",
            ["Living Room", "Bedroom", "Kitchen", "Bathroom", "Balcony", "Office", "Other"],
        )
        light = st.select_slider("Light Need", options=["low", "medium", "high"], value="medium")
        freq = st.number_input("Water every (hours)", min_value=1, max_value=2160, value=168)
        health = st.selectbox("Health Status", ["healthy", "needs_attention", "critical"])
        notes = st.text_area("Notes", max_chars=300)

        if st.button("Save", type="primary", use_container_width=True):
            if not name or not species:
                st.error("Name and Species are required.")
                return
            try:
                plant_api.create_plant(
                    {
                        "name": name,
                        "species": species,
                        "location": location,
                        "light_need": light,
                        "water_frequency_hours": freq,
                        "health_status": health,
                        "notes": notes,
                    }
                )
                cached_api.clear_cache()
                st.session_state["show_add_form"] = False
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to create plant: {exc}")

    add_dialog()

# ---------------------------------------------------------------------------
# Apply filters (from sidebar)
# ---------------------------------------------------------------------------
filtered = plants
if page == "Dashboard":
    if search:
        filtered = [p for p in filtered if search.lower() in p["name"].lower()]
    if filter_loc:
        filtered = [p for p in filtered if p["location"] in filter_loc]
    if filter_health:
        filtered = [p for p in filtered if p["health_status"] in filter_health]
    if filter_light:
        filtered = [p for p in filtered if p["light_need"] in filter_light]

# ---------------------------------------------------------------------------
# Plant card grid
# ---------------------------------------------------------------------------
if not filtered:
    st.markdown(
        """<div class="empty-state">
  <div class="empty-state-icon">🌵</div>
  <div class="empty-state-title">Your garden is empty</div>
  <div class="empty-state-text">Add your first plant to get started!</div>
</div>""",
        unsafe_allow_html=True,
    )
else:
    for i in range(0, len(filtered), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(filtered):
                break
            plant = filtered[idx]
            overdue = is_overdue(plant)

            with col:
                with st.container(border=True):
                    st.markdown(
                        plant_card_html(plant),
                        unsafe_allow_html=True,
                    )

                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        if st.button("💧", key=f"water_{plant['id']}", help="Water now"):
                            plant_api.patch_plant(
                                plant["id"],
                                {"last_watered": datetime.now(timezone.utc).isoformat()},
                            )
                            cached_api.clear_cache()
                            st.rerun()
                    with b2:
                        if st.button("✏️", key=f"edit_{plant['id']}", help="Edit"):
                            st.session_state[f"editing_{plant['id']}"] = True
                            st.rerun()
                    with b3:
                        if st.button("🗑️", key=f"del_{plant['id']}", help="Delete"):
                            st.session_state[f"confirm_del_{plant['id']}"] = True
                            st.rerun()
                    with b4:
                        if st.button("🤖", key=f"ai_{plant['id']}", help="AI care advice"):
                            advice = get_advice(plant["id"])
                            st.session_state[f"advice_{plant['id']}"] = advice

                    if st.session_state.get(f"advice_{plant['id']}"):
                        adv = st.session_state[f"advice_{plant['id']}"]
                        with st.expander("🤖 AI Advice", expanded=True):
                            st.caption(adv.get("summary", ""))
                            for tip in adv.get("tips", []):
                                st.markdown(f"- {tip}")
                            st.caption(f"Source: {adv.get('source', 'unknown')}")

        # Dialogs for plants in this row
        for j in range(3):
            idx = i + j
            if idx >= len(filtered):
                break
            plant = filtered[idx]

            # -- Edit dialog --
            if st.session_state.get(f"editing_{plant['id']}"):

                @st.dialog(f"Edit {plant['name']}")
                def edit_dialog(p=plant):
                    name = st.text_input("Name", value=p["name"])
                    species = st.text_input("Species", value=p["species"])
                    location = st.selectbox(
                        "Location",
                        ["Living Room", "Bedroom", "Kitchen", "Bathroom", "Balcony", "Office", "Other"],
                        index=["Living Room", "Bedroom", "Kitchen", "Bathroom", "Balcony", "Office", "Other"].index(p["location"])
                        if p["location"] in ["Living Room", "Bedroom", "Kitchen", "Bathroom", "Balcony", "Office", "Other"]
                        else 0,
                    )
                    light = st.select_slider(
                        "Light Need",
                        options=["low", "medium", "high"],
                        value=p["light_need"],
                    )
                    freq = st.number_input(
                        "Water every (hours)", min_value=1, max_value=2160, value=p["water_frequency_hours"]
                    )
                    health = st.selectbox(
                        "Health",
                        ["healthy", "needs_attention", "critical"],
                        index=["healthy", "needs_attention", "critical"].index(p["health_status"]),
                    )
                    notes = st.text_area("Notes", value=p.get("notes", ""), max_chars=300)

                    if st.button("Save Changes", type="primary", use_container_width=True):
                        try:
                            plant_api.update_plant(
                                p["id"],
                                {
                                    "name": name,
                                    "species": species,
                                    "location": location,
                                    "light_need": light,
                                    "water_frequency_hours": freq,
                                    "last_watered": p.get("last_watered", ""),
                                    "health_status": health,
                                    "image_url": p.get("image_url", ""),
                                    "notes": notes,
                                },
                            )
                            cached_api.clear_cache()
                            del st.session_state[f"editing_{p['id']}"]
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Update failed: {exc}")

                edit_dialog()

            # -- Delete confirmation --
            if st.session_state.get(f"confirm_del_{plant['id']}"):

                @st.dialog(f"Delete {plant['name']}?")
                def delete_dialog(p=plant):
                    st.warning(f"Are you sure you want to delete **{p['name']}**? This cannot be undone.")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button("Cancel", use_container_width=True):
                            del st.session_state[f"confirm_del_{p['id']}"]
                            st.rerun()
                    with dc2:
                        if st.button("Delete", type="primary", use_container_width=True):
                            try:
                                plant_api.delete_plant(p["id"])
                                cached_api.clear_cache()
                                del st.session_state[f"confirm_del_{p['id']}"]
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Delete failed: {exc}")

                delete_dialog()

# ---------------------------------------------------------------------------
# Export to JSON (small extra)
# ---------------------------------------------------------------------------
st.divider()
if plants:
    st.download_button(
        "📥 Export to JSON",
        data=json.dumps(plants, indent=2),
        file_name="plantpal_export.json",
        mime="application/json",
    )
