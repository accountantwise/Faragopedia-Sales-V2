from fastapi.testclient import TestClient
import sys
import os
import pytest
from unittest.mock import patch, AsyncMock

# Add the project root and backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock environment variable for OpenAI API key
os.environ["OPENAI_API_KEY"] = "sk-dummy"
os.environ["AI_PROVIDER"] = "openai"
os.environ["AI_MODEL"] = "gpt-4o-mini"

from backend.main import app

client = TestClient(app)

@patch("api.routes.wiki_manager.list_sources")
def test_list_sources(mock_list):
    mock_list.return_value = ["source1.txt", "source2.pdf"]
    response = client.get("/api/sources")
    assert response.status_code == 200
    assert response.json() == ["source1.txt", "source2.pdf"]

@patch("api.routes.wiki_manager.get_source_content", new_callable=AsyncMock)
def test_get_source(mock_get):
    mock_get.return_value = "Source Content"
    response = client.get("/api/sources/source1.txt")
    assert response.status_code == 200
    assert response.json() == {"content": "Source Content"}
    mock_get.assert_called_once_with("source1.txt")

@patch("api.routes.wiki_manager.get_source_content", new_callable=AsyncMock)
def test_get_source_not_found(mock_get):
    mock_get.side_effect = FileNotFoundError()
    response = client.get("/api/sources/nonexistent.txt")
    assert response.status_code == 404
