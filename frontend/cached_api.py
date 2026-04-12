import streamlit as st

import plant_api


@st.cache_data(ttl=2, show_spinner=False)
def get_plants():
    return plant_api.get_plants()


@st.cache_data(ttl=2, show_spinner=False)
def get_care_events(plant_id=None, event_type=None, limit=50):
    return plant_api.get_care_events(
        plant_id=plant_id, event_type=event_type, limit=limit
    )


def clear_cache():
    get_plants.clear()
    get_care_events.clear()
