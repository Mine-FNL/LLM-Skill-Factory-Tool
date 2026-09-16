from skill_factory.config import get_settings
from skill_factory.providers import DEFAULT_PROVIDER, PROVIDERS, get_provider, provider_ids


def test_registry_has_expected_providers():
    assert {"openrouter", "minimax", "kimi", "custom"} <= set(provider_ids())


def test_get_provider_fallback():
    assert get_provider("kimi").id == "kimi"
    assert get_provider("does-not-exist").id == DEFAULT_PROVIDER
    assert get_provider(None).id == DEFAULT_PROVIDER


def _clear_env(monkeypatch):
    for v in [
        "OPENROUTER_API_KEY",
        "MINIMAX_API_KEY",
        "MOONSHOT_API_KEY",
        "LLM_API_KEY",
        "LLM_PROVIDER",
        "SKILLS_DIR",
        "OPENROUTER_DEFAULT_MODEL",
        "MINIMAX_DEFAULT_MODEL",
        "KIMI_DEFAULT_MODEL",
    ]:
        monkeypatch.delenv(v, raising=False)


def test_default_is_openrouter(monkeypatch):
    _clear_env(monkeypatch)
    s = get_settings({})
    assert s.provider_id == "openrouter"
    assert s.base_url == PROVIDERS["openrouter"].base_url
    assert s.default_model == PROVIDERS["openrouter"].default_model
    assert s.sends_app_headers is True
    assert not s.has_key


def test_minimax_overrides(monkeypatch):
    _clear_env(monkeypatch)
    s = get_settings({"provider": "minimax", "api_key": "k", "default_model": "MiniMax-M1"})
    assert s.provider_id == "minimax"
    assert s.base_url == PROVIDERS["minimax"].base_url
    assert s.api_key == "k"
    assert s.default_model == "MiniMax-M1"
    assert s.supports_model_listing is False
    assert s.has_key


def test_key_resolved_from_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MOONSHOT_API_KEY", "envkey")
    s = get_settings({"provider": "kimi"})
    assert s.provider_id == "kimi"
    assert s.api_key == "envkey"


def test_default_model_from_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("KIMI_DEFAULT_MODEL", "kimi-latest")
    s = get_settings({"provider": "kimi"})
    assert s.default_model == "kimi-latest"


def test_base_url_override_for_regional_endpoint(monkeypatch):
    _clear_env(monkeypatch)
    s = get_settings({"provider": "kimi", "api_key": "k", "base_url": "https://api.moonshot.cn/v1"})
    assert s.base_url == "https://api.moonshot.cn/v1"


def test_custom_provider_requires_user_base_url(monkeypatch):
    _clear_env(monkeypatch)
    s = get_settings({"provider": "custom", "api_key": "k"})
    assert s.provider_id == "custom"
    assert s.base_url == ""


def test_provider_from_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    s = get_settings({})
    assert s.provider_id == "minimax"
