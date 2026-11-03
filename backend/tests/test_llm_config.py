import pytest

from app.llm.config import ConfigError, load_llm_settings

BASE = {"LLM_BASE_URL": "http://localhost:11434/v1", "LLM_MODEL": "mistral"}


def test_defaults():
    s = load_llm_settings(BASE)
    assert (s.base_url, s.model, s.api_key) == ("http://localhost:11434/v1", "mistral", None)
    assert (s.timeout_s, s.max_output_tokens, s.max_retries) == (60.0, 2048, 3)
    assert s.structured_output == "auto" and s.debug_log_content is False


def test_overrides():
    s = load_llm_settings({**BASE, "LLM_API_KEY": "k", "LLM_TIMEOUT_S": "120",
                           "LLM_MAX_OUTPUT_TOKENS": "4096", "LLM_STRUCTURED_OUTPUT": "json_object"})
    assert (s.api_key, s.timeout_s, s.max_output_tokens, s.structured_output) == ("k", 120.0, 4096, "json_object")


def test_missing_variables_are_listed():
    with pytest.raises(ConfigError, match="LLM_BASE_URL"):
        load_llm_settings({"LLM_MODEL": "m"})


@pytest.mark.parametrize("bad", [{"LLM_TIMEOUT_S": "abc"}, {"LLM_MAX_RETRIES": "x"}, {"LLM_STRUCTURED_OUTPUT": "xml"}])
def test_invalid_values_are_rejected(bad):
    with pytest.raises(ConfigError):
        load_llm_settings({**BASE, **bad})


def test_debug_content_logging_is_forbidden_in_production():
    assert load_llm_settings({**BASE, "LLM_DEBUG_LOG_CONTENT": "true"}).debug_log_content is True
    with pytest.raises(ConfigError, match="production"):
        load_llm_settings({**BASE, "LLM_DEBUG_LOG_CONTENT": "true", "APP_ENV": "production"})
