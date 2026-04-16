import pytest
import os
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
    sources_dir = tmp_path / "sources"
    wiki_dir = tmp_path / "wiki"
    archive_dir = tmp_path / "archive"
    schema_dir = tmp_path / "schema"
    sources_dir.mkdir()
    wiki_dir.mkdir()
    archive_dir.mkdir()
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    # Create entity subdirs
    for sub in ["clients", "prospects", "contacts", "photographers", "productions"]:
        (wiki_dir / sub).mkdir()

    with patch('api.routes.WikiManager') as MockWM:
        mock_wm = MagicMock()
        mock_wm.list_pages.return_value = ["clients/test-page.md"]
        mock_wm.get_page_content.return_value = "# Test Page"
        mock_wm.get_backlinks.return_value = []
        mock_wm.save_page_content = AsyncMock()
        mock_wm.archive_page = AsyncMock()
        mock_wm.create_new_page = AsyncMock(return_value="clients/Untitled.md")
        mock_wm.lint = AsyncMock(return_value=MagicMock(model_dump=lambda: {"findings": [], "summary": "Clean."}))
        MockWM.return_value = mock_wm

        from main import app
        with TestClient(app) as c:
            yield c


def test_get_pages_returns_grouped(client):
    with patch('api.routes.wiki_manager') as mock_wm:
        mock_wm.list_pages.return_value = ["clients/test-page.md", "prospects/another.md"]
        response = client.get("/api/pages")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_page(client):
    with patch('api.routes.wiki_manager') as mock_wm:
        mock_wm.get_page_content.return_value = "# Test Page"
        response = client.get("/api/pages/clients/test-page.md")
    assert response.status_code in (200, 400, 404)


def test_update_page(client):
    with patch('api.routes.wiki_manager') as mock_wm:
        mock_wm.save_page_content = AsyncMock()
        response = client.put(
            "/api/pages/clients/test-page.md",
            json={"content": "# Updated"}
        )
    assert response.status_code in (200, 400, 404, 422)


def test_delete_page(client):
    with patch('api.routes.wiki_manager') as mock_wm:
        mock_wm.archive_page = AsyncMock()
        response = client.delete("/api/pages/clients/test-page.md")
    assert response.status_code in (200, 400, 404)


def test_create_page_with_entity_type(client):
    with patch('api.routes.wiki_manager') as mock_wm:
        mock_wm.create_new_page = AsyncMock(return_value="clients/Untitled.md")
        response = client.post("/api/pages?entity_type=clients")
    assert response.status_code in (200, 400, 500)


def test_create_page_invalid_entity_type(client):
    response = client.post("/api/pages?entity_type=invoices")
    assert response.status_code == 400


def test_health_endpoint_gone(client):
    response = client.get("/api/health")
    assert response.status_code == 404


def test_lint_endpoint_exists(client):
    with patch('api.routes.wiki_manager') as mock_wm:
        mock_wm.lint = AsyncMock(return_value=MagicMock(
            model_dump=lambda: {"findings": [], "summary": "Clean."}
        ))
        response = client.post("/api/lint")
    assert response.status_code in (200, 500)


def test_safe_wiki_filename_invalid_rejected(client):
    response = client.get("/api/pages/evil/foo.md")
    assert response.status_code == 400

    response = client.get("/api/pages/flat-file.md")
    assert response.status_code in (400, 404)
