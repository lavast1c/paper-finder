import pytest

from paper_finder import config


@pytest.fixture(autouse=True)
def _no_supabase_env(monkeypatch, tmp_path):
    """No test may accidentally pick up a developer's real Supabase config.

    `create_app()` and `publish.resolve_db_url()` fall back to the environment and
    to a `.env` file at the project root; without this a green suite on a
    configured machine could be hitting (or trying to hit) the live project.
    """
    for var in (
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_DB_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    # resolve_db_url() reads `config.PROJECT_ROOT / ".env"` at call time -- point
    # it at an empty dir so the real repo `.env` never leaks into a test.
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
