import pytest

from skill_factory.llm_client import LLMClient, LLMError, OpenRouterError


def test_requires_api_key():
    with pytest.raises(LLMError):
        LLMClient("", base_url="https://x/v1", default_model="m")


def test_requires_base_url():
    with pytest.raises(LLMError):
        LLMClient("k", base_url="", default_model="m")


def test_backwards_compatible_alias():
    assert OpenRouterError is LLMError


def test_list_models_without_listing_uses_fallback():
    c = LLMClient(
        "k",
        base_url="https://x/v1",
        default_model="m",
        fallback_models=("a", "b"),
        supports_model_listing=False,
    )
    assert c.list_models() == ["a", "b"]


def test_app_headers_only_when_enabled():
    c = LLMClient("k", base_url="https://x/v1", default_model="m", send_app_headers=False)
    assert c._extra_headers == {}
    c2 = LLMClient(
        "k",
        base_url="https://x/v1",
        default_model="m",
        send_app_headers=True,
        app_title="T",
        app_url="https://u",
    )
    assert c2._extra_headers["X-Title"] == "T"
    assert c2._extra_headers["HTTP-Referer"] == "https://u"
