from clue.ai.llm import LLMError, complete_json, _extract_json
from clue.plugins.registry import discover
from pydantic import BaseModel
import pytest

from tests.conftest import signup


class Out(BaseModel):
    title: str


def test_health_and_setup_status(client):
    assert client.get("/api/health").json()["ok"] is True
    assert client.get("/api/setup/status").json()["has_key"] is False


def test_no_key_gives_friendly_error(db):
    with pytest.raises(LLMError, match="OpenRouter"):
        complete_json(db, Out, "sys", "user", feature="t")


def test_json_extraction():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Sure! {"a": 2} hope that helps') == {"a": 2}


def test_dev_mail_disabled_outside_self_host(client):
    assert client.get("/api/dev-mail").status_code == 404  # tests run in saas mode


def test_plugin_discovery_validates():
    for m in discover():
        assert "kind" in m and "name" in m


def test_plugins_endpoint_requires_login(client):
    assert client.get("/api/plugins").status_code == 401
    signup(client)
    assert client.get("/api/plugins").status_code == 200
