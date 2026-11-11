from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_settings_strip_pasted_whitespace():
    s = Settings(supabase_secret_key="  sb_secret_abc \n", gemini_api_key="key\n", _env_file=None)
    assert s.supabase_secret_key == "sb_secret_abc"
    assert s.gemini_api_key == "key"


def test_keys_lose_inner_whitespace_and_invisible_chars():
    s = Settings(supabase_secret_key="sb_secret_ab c\u200bd", supabase_url=" https://x.supabase.co ", _env_file=None)
    assert s.supabase_secret_key == "sb_secret_abcd"
    assert s.supabase_url == "https://x.supabase.co"


def test_unhandled_errors_keep_cors_headers(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    from app.core import config

    config.get_settings.cache_clear()
    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/boom", headers={"Origin": "https://app.example.com"})
    config.get_settings.cache_clear()
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert r.headers.get("access-control-allow-origin") == "https://app.example.com"
