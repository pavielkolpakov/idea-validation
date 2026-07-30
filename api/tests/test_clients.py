import pytest

from app.clients import build_clients


def test_missing_keys_fail_fast_with_an_actionable_message(monkeypatch):
    """Startup must say which key is missing and where to put it.

    Phase 2 made the app unbootable without provider keys. That's correct — it
    can't do anything useful without them — but the default failure is a vendor
    SDK exception raised from inside a constructor, which tells a new developer
    nothing about this project.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PERPLEXITY_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    with pytest.raises(RuntimeError) as exc:
        build_clients()

    message = str(exc.value)
    assert "PERPLEXITY_API_KEY" in message
    assert "ANTHROPIC_API_KEY" in message
    assert ".env" in message

    get_settings.cache_clear()
