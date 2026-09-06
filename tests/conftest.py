import pytest


@pytest.fixture(autouse=True)
def _no_supabase_env(monkeypatch):
    """No test may accidentally pick up a developer's real Supabase config.

    `create_app()` and `publish.resolve_db_url()` fall back to the environment /
    `.env`; without this a green suite on a configured machine could be hitting
    (or trying to hit) the live project.
    """
    for var in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_DB_URL"):
        monkeypatch.delenv(var, raising=False)
