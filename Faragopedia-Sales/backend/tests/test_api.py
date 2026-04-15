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

@patch("api.routes.wiki_manager.ingest_source", new_callable=AsyncMock)
def test_upload_file(mock_ingest):
    # In this test environment, sources is at ./sources from project root
    sources_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../sources"))
    if not os.path.exists(sources_dir):
        os.makedirs(sources_dir)
    
    filename = "test_upload.txt"
    content = b"hello world"
    files = {"file": (filename, content, "text/plain")}
    
    # Prefix with /api as planned in main.py
    response = client.post("/api/upload", files=files)
    
    assert response.status_code == 200
    assert response.json() == {"filename": filename, "message": "File uploaded and ingestion started"}
    
    # Verify ingest_source was called once with the correct filename
    mock_ingest.assert_called_once_with(filename)
    
    file_path = os.path.join(sources_dir, filename)
    assert os.path.exists(file_path)
    
    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)

def test_upload_missing_file():
    # Attempt to upload without 'file' parameter
    response = client.post("/api/upload")
    assert response.status_code == 422

@patch("api.routes.wiki_manager.query", new_callable=AsyncMock)
def test_chat_query(mock_query):
    mock_query.return_value = "Mocked LLM Response"
    query = "What is Faragopedia?"
    response = client.post(f"/api/chat?query={query}")
    
    assert response.status_code == 200
    assert response.json() == {"response": "Mocked LLM Response"}
    
    # Verify query was called once with the correct query
    mock_query.assert_called_once_with(query)

def test_chat_missing_query():
    # Attempt to chat without 'query' parameter
    response = client.post("/api/chat")
    assert response.status_code == 422

def test_chat_empty_query():
    # Attempt to chat with empty query
    response = client.post("/api/chat?query=")
    assert response.status_code == 422

def test_upload_empty_filename():
    # Attempt to upload with an empty filename
    files = {"file": ("", b"hello world", "text/plain")}
    response = client.post("/api/upload", files=files)
    # The current implementation sanitizes the filename using os.path.basename(""), which returns ""
    # then re.sub removes nothing, and it tries to write to the sources directory with an empty filename.
    # Actually, UploadFile.filename would be "" and os.path.join(SOURCES_DIR, "") is just SOURCES_DIR.
    # Then it tries to open SOURCES_DIR as a file in "wb" mode, which should raise an IsADirectoryError or similar.
    # In routes.py: with open(file_path, "wb") as buffer:
    # This will likely return 500 or 422 depending on how FastAPI handles it.
    assert response.status_code in [500, 422]

@patch("api.routes.wiki_manager.health_check")
def test_health_check(mock_health):
    mock_health.return_value = {
        "total_pages": 10,
        "orphan_pages": [],
        "missing_pages": [],
        "status": "healthy"
    }
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["total_pages"] == 10

@patch("api.routes.wiki_manager.list_pages")
def test_list_pages(mock_list):
    mock_list.return_value = ["page1.md", "page2.md"]
    response = client.get("/api/pages")
    assert response.status_code == 200
    assert response.json() == ["page1.md", "page2.md"]

@patch("api.routes.wiki_manager.get_page_content")
def test_get_page(mock_get):
    mock_get.return_value = "# Test Page Content"
    response = client.get("/api/pages/test.md")
    assert response.status_code == 200
    assert response.json() == {"content": "# Test Page Content"}

@patch("api.routes.wiki_manager.get_page_content")
def test_get_page_not_found(mock_get):
    mock_get.side_effect = FileNotFoundError()
    response = client.get("/api/pages/nonexistent.md")
    assert response.status_code == 404


# --- safe_wiki_filename unit tests ---

from api.routes import safe_wiki_filename

def test_safe_wiki_filename_plain():
    assert safe_wiki_filename("FastAPI.md") == "FastAPI.md"

def test_safe_wiki_filename_preserves_parens():
    # This is the real bug: secure_filename mangles these
    assert safe_wiki_filename("Agent_(Managed_Agents_Concept).md") == "Agent_(Managed_Agents_Concept).md"

def test_safe_wiki_filename_preserves_plus():
    assert safe_wiki_filename("Agent_SDK_+_Trigger.dev.md") == "Agent_SDK_+_Trigger.dev.md"

def test_safe_wiki_filename_strips_directory_components():
    # Path traversal attempt: basename strips the leading ../
    # The function must NOT raise — it just returns the safe basename
    result = safe_wiki_filename("../etc/passwd.md")
    assert result == "passwd.md"

def test_safe_wiki_filename_rejects_non_md():
    with pytest.raises(ValueError):
        safe_wiki_filename("passwd")

def test_safe_wiki_filename_rejects_non_md_with_traversal():
    with pytest.raises(ValueError):
        safe_wiki_filename("../etc/passwd")


# --- Route integration: GET /pages/{filename} passes correct name to get_page_content ---

@patch("api.routes.wiki_manager.get_page_content")
def test_get_page_preserves_parens_in_filename(mock_get):
    """Ensure the route does NOT mangle parentheses before calling get_page_content."""
    mock_get.return_value = "# Agent"
    response = client.get("/api/pages/Agent_(Managed_Agents_Concept).md")
    assert response.status_code == 200
    mock_get.assert_called_once_with("Agent_(Managed_Agents_Concept).md")

@patch("api.routes.wiki_manager.get_page_content")
def test_get_page_rejects_non_md(mock_get):
    """Filename without .md extension must return 400, not 404/500."""
    response = client.get("/api/pages/passwd")
    assert response.status_code == 400
    mock_get.assert_not_called()

@patch("api.routes.wiki_manager.create_new_page", new_callable=AsyncMock)
def test_create_page(mock_create):
    mock_create.return_value = "Untitled.md"
    response = client.post("/api/pages")
    assert response.status_code == 200
    assert response.json()["filename"] == "Untitled.md"
    mock_create.assert_called_once()

@patch("api.routes.wiki_manager.archive_page", new_callable=AsyncMock)
def test_delete_page_to_archive(mock_archive):
    mock_archive.return_value = None
    response = client.delete("/api/pages/test.md")
    assert response.status_code == 200
    assert response.json()["message"] == "Page moved to archive"
    mock_archive.assert_called_once_with("test.md")

@patch("api.routes.wiki_manager.archive_source", new_callable=AsyncMock)
def test_delete_source_to_archive(mock_archive):
    mock_archive.return_value = None
    response = client.delete("/api/sources/test.txt")
    assert response.status_code == 200
    assert response.json()["message"] == "Source moved to archive"
    mock_archive.assert_called_once_with("test.txt")

@patch("api.routes.wiki_manager.restore_page", new_callable=AsyncMock)
def test_restore_page(mock_restore):
    mock_restore.return_value = None
    response = client.post("/api/archive/pages/test.md/restore")
    assert response.status_code == 200
    assert response.json()["message"] == "Page restored from archive"
    mock_restore.assert_called_once_with("test.md")

@patch("api.routes.wiki_manager.delete_archived_page", new_callable=AsyncMock)
def test_delete_permanent(mock_delete):
    mock_delete.return_value = None
    response = client.delete("/api/archive/pages/test.md/permanent")
    assert response.status_code == 200
    assert response.json()["message"] == "Page permanently deleted from archive"
    mock_delete.assert_called_once_with("test.md")

def test_download_page():
    # We need a real file for FileResponse or mock it heavily
    # Let's create a dummy file in the wiki dir
    wiki_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../wiki"))
    if not os.path.exists(wiki_dir):
        os.makedirs(wiki_dir)
    
    filename = "download_test.md"
    path = os.path.join(wiki_dir, filename)
    with open(path, "w") as f:
        f.write("# Download Test")
    
    try:
        response = client.get(f"/api/pages/{filename}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        assert b"Download Test" in response.content
    finally:
        if os.path.exists(path):
            os.remove(path)

@patch("api.routes.wiki_manager.ingest_source", new_callable=AsyncMock)
def test_upload_no_ingest(mock_ingest):
    filename = "test_no_ingest.txt"
    content = b"hello"
    files = {"file": (filename, content, "text/plain")}
    
    # Request with ingest=false
    response = client.post("/api/upload?ingest=false", files=files)
    
    assert response.status_code == 200
    assert "ingestion skipped" in response.json()["message"]
    # Verify ingest_source was NOT called
    mock_ingest.assert_not_called()
    
    # Cleanup dummy file created by the actual route
    sources_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../sources"))
    path = os.path.join(sources_dir, filename)
    if os.path.exists(path):
        os.remove(path)

@patch("api.routes.wiki_manager.get_sources_metadata")
def test_get_metadata(mock_meta):
    mock_meta.return_value = {"test.txt": {"ingested": True, "ingested_at": "now"}}
    response = client.get("/api/sources/metadata")
    assert response.status_code == 200
    assert response.json()["test.txt"]["ingested"] is True

@patch("api.routes.wiki_manager.ingest_source", new_callable=AsyncMock)
def test_manual_ingest(mock_ingest):
    filename = "manual_test.txt"
    # Ensure file exists so the route doesn't 404
    sources_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../sources"))
    if not os.path.exists(sources_dir):
        os.makedirs(sources_dir)
    path = os.path.join(sources_dir, filename)
    with open(path, "w") as f:
        f.write("test")
        
    try:
        response = client.post(f"/api/sources/{filename}/ingest")
        assert response.status_code == 200
        assert "Ingestion started" in response.json()["message"]
        mock_ingest.assert_called_once_with(filename)
    finally:
        if os.path.exists(path):
            os.remove(path)
