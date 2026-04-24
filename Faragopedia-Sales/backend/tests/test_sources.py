from fastapi.testclient import TestClient
import sys
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Add the project root and backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock environment variable for OpenAI API key
os.environ["OPENAI_API_KEY"] = "sk-dummy"
os.environ["AI_PROVIDER"] = "openai"
os.environ["AI_MODEL"] = "gpt-4o-mini"

from main import app
from api.routes import set_wiki_manager

client = TestClient(app)


def test_list_sources():
    mock_wm = MagicMock()
    mock_wm.list_sources.return_value = ["source1.txt", "source2.pdf"]
    set_wiki_manager(mock_wm)
    response = client.get("/api/sources")
    set_wiki_manager(None)
    assert response.status_code == 200
    assert response.json() == ["source1.txt", "source2.pdf"]


def test_get_source():
    mock_wm = MagicMock()
    mock_wm.get_source_content = AsyncMock(return_value="Source Content")
    set_wiki_manager(mock_wm)
    response = client.get("/api/sources/source1.txt")
    set_wiki_manager(None)
    assert response.status_code == 200
    assert response.json() == {"content": "Source Content"}


def test_get_source_not_found():
    mock_wm = MagicMock()
    mock_wm.get_source_content = AsyncMock(side_effect=FileNotFoundError())
    set_wiki_manager(mock_wm)
    response = client.get("/api/sources/nonexistent.txt")
    set_wiki_manager(None)
    assert response.status_code == 404


# ── Paste endpoint ────────────────────────────────────────────────────────────

def test_paste_source_happy_path(tmp_path):
    with patch("api.routes.get_sources_dir", return_value=str(tmp_path)):
        response = client.post("/api/paste", json={"content": "Hello world"})
    assert response.status_code == 200
    data = response.json()
    assert "filename" in data
    assert data["filename"].startswith("paste-")
    assert data["filename"].endswith(".txt")
    assert (tmp_path / data["filename"]).read_text(encoding="utf-8") == "Hello world"


def test_paste_source_with_custom_name(tmp_path):
    with patch("api.routes.get_sources_dir", return_value=str(tmp_path)):
        response = client.post("/api/paste", json={"content": "Notes", "name": "my notes"})
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "my_notes.txt"
    assert (tmp_path / "my_notes.txt").read_text(encoding="utf-8") == "Notes"


def test_paste_source_empty_content():
    response = client.post("/api/paste", json={"content": "   "})
    assert response.status_code == 422


# ── Scrape URLs endpoint ──────────────────────────────────────────────────────

def test_scrape_urls_starts_background_jobs():
    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc"}):
        with patch("api.routes._crawl_and_save", new_callable=AsyncMock):
            response = client.post(
                "/api/scrape-urls",
                json={"urls": ["https://example.com", "https://other.com"]},
            )
    assert response.status_code == 202
    assert response.json()["message"] == "Started 2 crawl job(s)"


def test_scrape_urls_empty_list():
    with patch.dict(os.environ, {"WISECRAWLER_BASE_URL": "http://test-wc"}):
        response = client.post("/api/scrape-urls", json={"urls": []})
    assert response.status_code == 422


def test_scrape_urls_no_wisecrawler_url():
    env = {k: v for k, v in os.environ.items() if k != "WISECRAWLER_BASE_URL"}
    with patch.dict(os.environ, env, clear=True):
        response = client.post("/api/scrape-urls", json={"urls": ["https://example.com"]})
    assert response.status_code == 503
