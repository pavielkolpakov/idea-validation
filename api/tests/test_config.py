"""`.env` must reach `os.environ`, not just `Settings`.

pydantic-settings parses `.env` into the `Settings` object and stops there. Any
library that reads `os.environ` directly — LangSmith's tracer is the one that
matters here — sees nothing, so tracing silently never happens even with every
key correctly set in the file. Nothing errors; traces just never appear.
"""

import os

from app.config import load_env_file


def test_env_file_is_exported_to_os_environ(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('LANGSMITH_TRACING=true\nLANGSMITH_PROJECT="quoted-name"\n')

    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    load_env_file(env)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    # Quotes are a file-format artifact; a consumer reading os.environ must not
    # receive them as part of the value.
    assert os.environ["LANGSMITH_PROJECT"] == "quoted-name"


def test_real_environment_wins_over_the_file(tmp_path, monkeypatch):
    """An explicitly exported var must not be clobbered by the file.

    This is what keeps the test suite pointed at `ideacheck_test`: conftest sets
    DATABASE_URL before app import, and the developer's `.env` names the dev
    database.
    """
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgresql+psycopg://from-the-file/dev\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://already-set/test")

    load_env_file(env)

    assert os.environ["DATABASE_URL"] == "postgresql+psycopg://already-set/test"


def test_missing_env_file_is_not_an_error(tmp_path):
    load_env_file(tmp_path / "does-not-exist")
