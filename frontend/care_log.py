from datetime import date

import streamlit as st

import plant_api
import cached_api


def days_since_watered(last_watered: str | None) -> int | None:
    if not last_watered:
        return None
    try:
        return (date.today() - date.fromisoformat(last_watered)).days
    except ValueError:
        return None


def render():
    st.markdown("# 📋 Care Log")
    st.caption("Track watering schedules and spot overdue plants at a glance.")

    plants = cached_api.get_plants()

    if not plants:
        st.info("No plants yet. Head to the Dashboard to add some!")
        return

    # -------------------------------------------------------------------
    # Summary metrics
    # -------------------------------------------------------------------
    overdue_plants = []
    healthy_count = 0
    attention_count = 0
    critical_count = 0
    watered_today_count = 0

    for p in plants:
        days = days_since_watered(p.get("last_watered"))
        if days is not None and days > p.get("water_frequency_days", 7):
            overdue_plants.append({**p, "_days_overdue": days - p["water_frequency_days"]})
        if p.get("health_status") == "healthy":
            healthy_count += 1
        elif p.get("health_status") == "needs_attention":
            attention_count += 1
        elif p.get("health_status") == "critical":
            critical_count += 1
        if days == 0:
            watered_today_count += 1

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🌿 Healthy", healthy_count)
    m2.metric("🟡 Needs Attention", attention_count)
    m3.metric("🔴 Critical", critical_count)
    m4.metric("💧 Watered Today", watered_today_count)

    st.divider()

    # -------------------------------------------------------------------
    # Overdue alerts
    # -------------------------------------------------------------------
    if overdue_plants:
        st.markdown("### ⚠️ Overdue — Need Watering")
        overdue_plants.sort(key=lambda x: x["_days_overdue"], reverse=True)
        for p in overdue_plants:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 2])
                with c1:
                    st.markdown(f"**{p['name']}** — _{p['species']}_")
                with c2:
                    st.error(
                        f"Overdue by **{p['_days_overdue']}** day(s)  "
                        f"(last watered: {p.get('last_watered', 'never')})"
                    )
                with c3:
                    if st.button(
                        "💧 Water Now",
                        key=f"care_water_{p['id']}",
                        use_container_width=True,
                    ):
                        plant_api.patch_plant(
                            p["id"], {"last_watered": date.today().isoformat()}
                        )
                        cached_api.clear_cache()
                        st.rerun()
        st.divider()
    else:
        st.success("All plants are on schedule! No overdue watering.", icon="✅")
        st.divider()

    # -------------------------------------------------------------------
    # Full schedule table
    # -------------------------------------------------------------------
    st.markdown("### 🗓️ Watering Schedule")

    rows = []
    for p in plants:
        days = days_since_watered(p.get("last_watered"))
        next_in = (
            max(0, p.get("water_frequency_days", 7) - days) if days is not None else None
        )

        health = p.get("health_status", "unknown")
        health_display = {"healthy": "🟢 Healthy", "needs_attention": "🟡 Attention", "critical": "🔴 Critical"}.get(health, health)

        if days is not None and days > p.get("water_frequency_days", 7):
            water_status = "⚠️ OVERDUE"
        elif days == 0:
            water_status = "💧 Watered today"
        else:
            water_status = "✅ OK"

        rows.append(
            {
                "Name": p["name"],
                "Species": p["species"],
                "Location": p["location"],
                "Health": health_display,
                "Every (days)": p["water_frequency_days"],
                "Last Watered": p.get("last_watered") or "Never",
                "Days Ago": days if days is not None else "—",
                "Next In": f"{next_in} days" if next_in is not None else "—",
                "Watering": water_status,
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)
