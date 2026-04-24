import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app
from app.security import create_access_token

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(autouse=True)
def _disable_external_ratelimit(monkeypatch):
    """Bypass Redis-backed rate limiting / caching in unit tests."""
    from app import cache as cache_module
    from app import rate_limit as rate_limit_module
    from app.routers import plants as plants_router

    monkeypatch.setattr(plants_router.get_settings, "cache_clear", lambda: None, raising=False)

    async def noop_async(*_, **__):
        return None

    async def passthrough_idempotency(*_, **__):
        return True

    async def noop_cache_get(*_, **__):
        return None

    monkeypatch.setattr(cache_module, "cache_get", noop_cache_get)
    monkeypatch.setattr(cache_module, "cache_set", noop_async)
    monkeypatch.setattr(cache_module, "cache_delete", noop_async)
    monkeypatch.setattr(cache_module, "invalidate_plants_cache", noop_async)
    monkeypatch.setattr(cache_module, "idempotency_check_and_set", passthrough_idempotency)

    # Also patch the names already imported into plants router / rate_limit.
    monkeypatch.setattr(plants_router, "cache_get", noop_cache_get)
    monkeypatch.setattr(plants_router, "cache_set", noop_async)
    monkeypatch.setattr(plants_router, "invalidate_plants_cache", noop_async)

    class _FakeRedis:
        async def incr(self, *_):
            return 1

        async def expire(self, *_):
            return True

    async def fake_dispatch(self, request, call_next):
        return await call_next(request)

    monkeypatch.setattr(rate_limit_module.RateLimitMiddleware, "dispatch", fake_dispatch)


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="editor_token")
def editor_token_fixture() -> str:
    return create_access_token(subject="test-editor", roles=["editor"])


@pytest.fixture(name="viewer_token")
def viewer_token_fixture() -> str:
    return create_access_token(subject="test-viewer", roles=["viewer"])


@pytest.fixture(name="client")
def client_fixture(session: Session, editor_token: str):
    def _override():
        return session

    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {editor_token}"})
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="anon_client")
def anon_client_fixture(session: Session):
    """TestClient without any auth headers — for 401/403 checks."""

    def _override():
        return session

    app.dependency_overrides[get_session] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
