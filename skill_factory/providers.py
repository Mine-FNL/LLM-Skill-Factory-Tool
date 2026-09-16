"""Provider registry.

Every supported provider exposes an OpenAI-compatible Chat Completions API, so a
single client (see ``llm_client.py``) drives all of them — only the base URL, API
key, and model ids differ. Base URLs and models are editable in the UI, so regional
endpoints (e.g. Moonshot .ai vs .cn) or new model ids can be set without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    base_url: str
    api_key_env: str
    default_model: str
    # Curated fallback model list (used when live listing is unsupported or fails).
    models: tuple[str, ...] = field(default_factory=tuple)
    # Whether GET {base_url}/models returns a usable list.
    supports_model_listing: bool = True
    # OpenRouter-specific attribution headers (harmless elsewhere, but only sent for OR).
    sends_app_headers: bool = False
    # Where to get a key / notes shown in the UI.
    keys_url: str = ""
    note: str = ""


PROVIDERS: dict[str, Provider] = {
    "openrouter": Provider(
        id="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        default_model="anthropic/claude-sonnet-4.6",
        models=(
            "anthropic/claude-sonnet-4.6",
            "anthropic/claude-opus-4.1",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "google/gemini-2.5-pro",
            "x-ai/grok-2",
            "meta-llama/llama-3.3-70b-instruct",
        ),
        supports_model_listing=True,
        sends_app_headers=True,
        keys_url="https://openrouter.ai/keys",
        note="Aggregator: one key, hundreds of models. Click 'Fetch models' for the live list.",
    ),
    "minimax": Provider(
        id="minimax",
        label="MiniMax",
        base_url="https://api.minimax.io/v1",
        api_key_env="MINIMAX_API_KEY",
        default_model="MiniMax-M3",
        models=("MiniMax-M3", "MiniMax-M2.1", "MiniMax-M1", "MiniMax-Text-01"),
        supports_model_listing=False,
        keys_url="https://platform.minimax.io/",
        note="MiniMax's OpenAI-compatible endpoint (POST /v1/chat/completions). For the China "
        "platform, set the base URL to https://api.minimax.chat/v1 in Advanced. Model ids "
        "evolve (M2.x, M3…) — type the one you want.",
    ),
    "kimi": Provider(
        id="kimi",
        label="Kimi (Moonshot)",
        base_url="https://api.moonshot.ai/v1",
        api_key_env="MOONSHOT_API_KEY",
        default_model="kimi-k2.6",
        models=(
            "kimi-k2.6",
            "kimi-k2.5",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ),
        supports_model_listing=True,
        keys_url="https://platform.moonshot.ai/console/api-keys",
        note="Moonshot AI (Kimi). For the China platform, set the base URL to "
        "https://api.moonshot.cn/v1 in Advanced. Click 'Fetch models' for the live list "
        "(the older kimi-k2 / kimi-latest ids were retired in 2026).",
    ),
    "custom": Provider(
        id="custom",
        label="Custom (OpenAI-compatible)",
        base_url="",
        api_key_env="LLM_API_KEY",
        default_model="",
        models=(),
        supports_model_listing=True,
        keys_url="",
        note="Point at any OpenAI-compatible endpoint: set the Base URL, key, and model.",
    ),
}

DEFAULT_PROVIDER = "openrouter"


def get_provider(provider_id: str | None) -> Provider:
    return PROVIDERS.get(provider_id or "", PROVIDERS[DEFAULT_PROVIDER])


def provider_ids() -> list[str]:
    return list(PROVIDERS.keys())
