import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "AI_PROVIDER": "openai",
        "AI_MODEL": "gpt-4o-mini"
    }):
        yield


@pytest.fixture
def client(tmp_path):
    from api.routes import set_wiki_manager
    mock_wm = MagicMock()
    mock_wm.get_pages_metadata.return_value = {
        "clients/acme.md": {"read": False, "read_at": None}
    }
    mock_wm.mark_page_read = AsyncMock(return_value=None)
    set_wiki_manager(mock_wm)

    from main import app
    with TestClient(app) as c:
        yield c, mock_wm

    set_wiki_manager(None)


def test_get_pages_metadata(client):
    c, mock_wm = client
    res = c.get("/api/pages/metadata")
    assert res.status_code == 200
    data = res.json()
    assert "clients/acme.md" in data
    assert data["clients/acme.md"]["read"] is False


def test_post_mark_read(client):
    c, mock_wm = client
    res = c.post("/api/pages/mark-read", json={"path": "clients/acme.md"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    mock_wm.mark_page_read.assert_called_once_with("clients/acme.md")
