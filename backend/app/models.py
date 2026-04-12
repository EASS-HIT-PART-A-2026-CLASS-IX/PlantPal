from sqlmodel import SQLModel, Field


class PlantBase(SQLModel):
    name: str = Field(index=True)
    species: str
    location: str = "Unknown"
    light_need: str = "medium"
    water_frequency_hours: int = 168  # default 7 days = 168 hours
    last_watered: str | None = None  # ISO datetime string
    health_status: str = "healthy"
    image_url: str = ""
    notes: str = ""


class Plant(PlantBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class PlantCreate(PlantBase):
    pass


class PlantRead(PlantBase):
    id: int


class PlantUpdate(SQLModel):
    name: str | None = None
    species: str | None = None
    location: str | None = None
    light_need: str | None = None
    water_frequency_hours: int | None = None
    last_watered: str | None = None
    health_status: str | None = None
    image_url: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Care Events
# ---------------------------------------------------------------------------

class CareEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    plant_id: int = Field(foreign_key="plant.id", index=True)
    event_type: str  # "watered", "health_changed", "note"
    detail: str = ""
    created_at: str = ""


class CareEventCreate(SQLModel):
    plant_id: int
    event_type: str = "note"
    detail: str = ""


class CareEventRead(SQLModel):
    id: int
    plant_id: int
    event_type: str
    detail: str
    created_at: str
    plant_name: str | None = None
