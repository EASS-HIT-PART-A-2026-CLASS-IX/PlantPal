from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import streamlit as st

import plant_api
import cached_api

EVENT_ICONS = {
    "watered": "💧",
    "health_changed": "🩺",
    "note": "📝",
}


def _parse_dt(iso: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _day_label(dt: datetime) -> str:
    today = datetime.now(timezone.utc).date()
    d = dt.date()
    if d == today:
        return "Today"
    if d == today - timedelta(days=1):
        return "Yesterday"
    return d.strftime("%b %d, %Y")


def _compute_streak(events: list[dict]) -> int:
    """Consecutive days (ending today or yesterday) with at least one watering."""
    water_dates: set[str] = set()
    for e in events:
        if e.get("event_type") != "watered":
            continue
        dt = _parse_dt(e.get("created_at", ""))
        if dt:
            water_dates.add(dt.date().isoformat())

    if not water_dates:
        return 0

    day = datetime.now(timezone.utc).date()
    if day.isoformat() not in water_dates:
        day -= timedelta(days=1)
    if day.isoformat() not in water_dates:
        return 0

    streak = 0
    while day.isoformat() in water_dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def render():
    st.markdown("# 📋 Care Log")
    st.caption("Your plant care history, insights, and notes — all in one place.")

    plants = cached_api.get_plants()
    all_events = cached_api.get_care_events(limit=200)

    if not plants:
        st.info("No plants yet. Head to the Dashboard to add some!")
        return

    plant_map = {p["id"]: p for p in plants}

    # -------------------------------------------------------------------
    # Section 1 — Summary Stats
    # -------------------------------------------------------------------
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    this_week = 0
    this_month = 0
    water_counts: Counter = Counter()

    for e in all_events:
        dt = _parse_dt(e.get("created_at", ""))
        if dt and dt >= week_ago:
            this_week += 1
        if dt and dt >= month_ago:
            this_month += 1
        if e.get("event_type") == "watered":
            water_counts[e["plant_id"]] += 1

    streak = _compute_streak(all_events)

    most_pampered = "—"
    if water_counts:
        pid = water_counts.most_common(1)[0][0]
        most_pampered = plant_map.get(pid, {}).get("name", f"#{pid}")

    most_neglected = "—"
    if water_counts and len(plants) > 1:
        all_ids = {p["id"] for p in plants}
        watered_ids = set(water_counts.keys())
        never_watered = all_ids - watered_ids
        if never_watered:
            pid = next(iter(never_watered))
            most_neglected = plant_map.get(pid, {}).get("name", f"#{pid}")
        else:
            pid = water_counts.most_common()[-1][0]
            most_neglected = plant_map.get(pid, {}).get("name", f"#{pid}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("This Week", this_week, help="Care actions in the last 7 days")
    m2.metric("This Month", this_month, help="Care actions in the last 30 days")
    m3.metric("🔥 Streak", f"{streak} day{'s' if streak != 1 else ''}")
    m4.metric("⭐ Most Pampered", most_pampered)

    st.divider()

    # -------------------------------------------------------------------
    # Section 2 — Activity Timeline
    # -------------------------------------------------------------------
    st.markdown("### 🕐 Activity Timeline")

    fc1, fc2 = st.columns(2)
    with fc1:
        plant_names = ["All Plants"] + sorted(p["name"] for p in plants)
        selected_plant_name = st.selectbox(
            "Filter by plant", plant_names, key="timeline_plant_filter"
        )
    with fc2:
        type_options = ["All Types", "watered", "health_changed", "note"]
        selected_type = st.selectbox(
            "Filter by event type", type_options, key="timeline_type_filter"
        )

    filtered = all_events
    if selected_plant_name != "All Plants":
        pid = next(
            (p["id"] for p in plants if p["name"] == selected_plant_name), None
        )
        if pid is not None:
            filtered = [e for e in filtered if e["plant_id"] == pid]
    if selected_type != "All Types":
        filtered = [e for e in filtered if e["event_type"] == selected_type]

    if not filtered:
        st.info("No events match your filters.")
    else:
        grouped: defaultdict[str, list] = defaultdict(list)
        for e in filtered:
            dt = _parse_dt(e.get("created_at", ""))
            label = _day_label(dt) if dt else "Unknown"
            grouped[label].append((dt, e))

        for day_label, items in grouped.items():
            st.markdown(f"**{day_label}**")
            items.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            for dt, e in items:
                icon = EVENT_ICONS.get(e["event_type"], "📌")
                time_str = dt.strftime("%H:%M") if dt else ""
                pname = e.get("plant_name") or plant_map.get(e["plant_id"], {}).get("name", "?")
                detail = f" — {e['detail']}" if e.get("detail") else ""

                with st.container(border=True):
                    c1, c2 = st.columns([1, 5])
                    with c1:
                        st.markdown(f"### {icon}")
                    with c2:
                        st.markdown(f"**{pname}** · {e['event_type'].replace('_', ' ')}{detail}")
                        st.caption(time_str)

    st.divider()

    # -------------------------------------------------------------------
    # Section 3 — Per-Plant Drilldown
    # -------------------------------------------------------------------
    st.markdown("### 🌱 Plant Drilldown")

    plant_choice = st.selectbox(
        "Select a plant",
        [p["name"] for p in plants],
        key="drilldown_plant",
    )
    chosen = next((p for p in plants if p["name"] == plant_choice), None)
    if not chosen:
        return

    plant_events = [e for e in all_events if e["plant_id"] == chosen["id"]]
    water_events = [e for e in plant_events if e["event_type"] == "watered"]

    total_waterings = len(water_events)
    if total_waterings >= 2:
        dates = sorted(
            _parse_dt(e["created_at"]) for e in water_events if _parse_dt(e["created_at"])
        )
        if len(dates) >= 2:
            gaps = [(dates[i] - dates[i - 1]).total_seconds() / 86400 for i in range(1, len(dates))]
            avg_gap = sum(gaps) / len(gaps)
            avg_text = f"{avg_gap:.1f} days"
        else:
            avg_text = "—"
    else:
        avg_text = "—"

    last_water_dt = None
    if water_events:
        last_water_dt = max(
            (_parse_dt(e["created_at"]) for e in water_events if _parse_dt(e["created_at"])),
            default=None,
        )
    if last_water_dt:
        ago = now - last_water_dt
        if ago.total_seconds() < 3600:
            last_text = f"{int(ago.total_seconds() / 60)} min ago"
        elif ago.total_seconds() < 86400:
            last_text = f"{int(ago.total_seconds() / 3600)}h ago"
        else:
            last_text = f"{int(ago.days)}d ago"
    else:
        last_text = "Never"

    s1, s2, s3 = st.columns(3)
    s1.metric("Total Waterings", total_waterings)
    s2.metric("Avg. Interval", avg_text)
    s3.metric("Last Watered", last_text)

    if plant_events:
        st.markdown("#### History")
        for e in plant_events:
            dt = _parse_dt(e.get("created_at", ""))
            icon = EVENT_ICONS.get(e["event_type"], "📌")
            time_str = dt.strftime("%Y-%m-%d %H:%M") if dt else ""
            detail = f" — {e['detail']}" if e.get("detail") else ""
            st.markdown(f"{icon} **{e['event_type'].replace('_', ' ')}**{detail}  \n`{time_str}`")
    else:
        st.info("No care events recorded for this plant yet.")

    st.divider()

    # -------------------------------------------------------------------
    # Add a care note
    # -------------------------------------------------------------------
    st.markdown("#### 📝 Add a Care Note")
    note_text = st.text_area(
        "Note", placeholder="e.g. Repotted into larger pot, noticed yellowing leaves…",
        key="care_note_input", max_chars=300,
    )
    if st.button("Save Note", type="primary", key="save_care_note"):
        if not note_text.strip():
            st.warning("Please enter a note first.")
        else:
            try:
                plant_api.create_care_event({
                    "plant_id": chosen["id"],
                    "event_type": "note",
                    "detail": note_text.strip(),
                })
                cached_api.clear_cache()
                st.success("Note saved!")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save note: {exc}")
