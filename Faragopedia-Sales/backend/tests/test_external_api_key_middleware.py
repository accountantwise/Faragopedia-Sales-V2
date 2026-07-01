import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "AI_PROVIDER": "openai",
        "AI_MODEL": "gpt-4o-mini",
    }):
        yield


@pytest.fixture
def client():
    from api.routes import set_wiki_manager
    mock_wm = MagicMock()
    mock_wm.get_pages_metadata.return_value = {}
    set_wiki_manager(mock_wm)

    from main import app
    with TestClient(app) as c:
        yield c

    set_wiki_manager(None)


EXTERNAL_ENV = {
    "FARAGOPEDIA_API_KEY": "secret123",
    "FARAGOPEDIA_API_HOSTNAME": "faragopedia-api.ai-wise.uk",
}


def test_internal_request_bypasses_key_check(client):
    with patch.dict(os.environ, EXTERNAL_ENV):
        res = client.get("/api/pages/metadata")
    assert res.status_code == 200


def test_frontend_request_with_cf_header_is_not_gated(client):
    # Regression test: Cloudflare injects CF-Connecting-IP on ALL tunneled
    # requests, including normal browser visits to the main frontend
    # hostname — not just the dedicated external-API hostname. A request
    # carrying that header but arriving on the frontend's Host must NOT be
    # blocked, or every real user gets locked out (2026-07-01 incident).
    with patch.dict(os.environ, EXTERNAL_ENV):
        res = client.get(
            "/api/pages/metadata",
            headers={"CF-Connecting-IP": "1.2.3.4", "Host": "faragopedia.ai-wise.uk"},
        )
    assert res.status_code == 200


def test_external_request_without_key_is_rejected(client):
    with patch.dict(os.environ, EXTERNAL_ENV):
        res = client.get(
            "/api/pages/metadata",
            headers={"CF-Connecting-IP": "1.2.3.4", "Host": "faragopedia-api.ai-wise.uk"},
        )
    assert res.status_code == 401


def test_external_request_with_wrong_key_is_rejected(client):
    with patch.dict(os.environ, EXTERNAL_ENV):
        res = client.get(
            "/api/pages/metadata",
            headers={
                "CF-Connecting-IP": "1.2.3.4",
                "Host": "faragopedia-api.ai-wise.uk",
                "X-API-Key": "wrong",
            },
        )
    assert res.status_code == 401


def test_external_request_with_correct_key_is_allowed(client):
    with patch.dict(os.environ, EXTERNAL_ENV):
        res = client.get(
            "/api/pages/metadata",
            headers={
                "CF-Connecting-IP": "1.2.3.4",
                "Host": "faragopedia-api.ai-wise.uk",
                "X-API-Key": "secret123",
            },
        )
    assert res.status_code == 200


def test_external_request_bypasses_check_when_key_unset(client):
    with patch.dict(os.environ, {"FARAGOPEDIA_API_HOSTNAME": "faragopedia-api.ai-wise.uk"}, clear=False):
        os.environ.pop("FARAGOPEDIA_API_KEY", None)
        res = client.get(
            "/api/pages/metadata",
            headers={"CF-Connecting-IP": "1.2.3.4", "Host": "faragopedia-api.ai-wise.uk"},
        )
    assert res.status_code == 200


def test_external_request_bypasses_check_when_hostname_unset(client):
    with patch.dict(os.environ, {"FARAGOPEDIA_API_KEY": "secret123"}, clear=False):
        os.environ.pop("FARAGOPEDIA_API_HOSTNAME", None)
        res = client.get(
            "/api/pages/metadata",
            headers={"CF-Connecting-IP": "1.2.3.4", "Host": "faragopedia-api.ai-wise.uk"},
        )
    assert res.status_code == 200


def test_non_api_route_is_not_gated(client):
    with patch.dict(os.environ, EXTERNAL_ENV):
        res = client.get("/", headers={"CF-Connecting-IP": "1.2.3.4", "Host": "faragopedia-api.ai-wise.uk"})
    assert res.status_code == 200
