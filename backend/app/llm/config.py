"""Lecture de la configuration du client LLM depuis les variables d'environnement (.env)."""
from __future__ import annotations

import os
from typing import Mapping

from .client import LLMSettings


class ConfigError(ValueError):
    pass


_STRUCTURED = {"auto", "json_schema", "json_object", "none"}


def _num(env, name, default, cast):
    raw = env.get(name)
    if raw in (None, ""):
        return default
    try:
        return cast(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} invalide : {raw!r}") from exc


def load_llm_settings(env: Mapping[str, str] | None = None) -> LLMSettings:
    env = os.environ if env is None else env
    missing = [n for n in ("LLM_BASE_URL", "LLM_MODEL") if not env.get(n)]
    if missing:
        raise ConfigError("Variables manquantes : " + ", ".join(missing))

    structured = env.get("LLM_STRUCTURED_OUTPUT", "auto")
    if structured not in _STRUCTURED:
        raise ConfigError(f"LLM_STRUCTURED_OUTPUT doit valoir l'un de {sorted(_STRUCTURED)}")

    debug = env.get("LLM_DEBUG_LOG_CONTENT", "false").strip().lower() in ("1", "true", "yes")
    if debug and env.get("APP_ENV", "").strip().lower() == "production":
        raise ConfigError("LLM_DEBUG_LOG_CONTENT est interdit en production (confidentialité).")

    return LLMSettings(
        base_url=env["LLM_BASE_URL"],
        model=env["LLM_MODEL"],
        api_key=env.get("LLM_API_KEY") or None,
        timeout_s=_num(env, "LLM_TIMEOUT_S", 60.0, float),
        max_output_tokens=_num(env, "LLM_MAX_OUTPUT_TOKENS", 2048, int),
        max_retries=_num(env, "LLM_MAX_RETRIES", 3, int),
        structured_output=structured,
        debug_log_content=debug,
    )
