import asyncio
import os
import pytest
from unittest.mock import MagicMock, patch

from agent.wiki_manager import WikiManager


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-4")


@pytest.fixture
def wm(tmp_path, mock_env):
    return WikiManager(
        sources_dir=str(tmp_path / "sources"),
        wiki_dir=str(tmp_path / "wiki"),
        archive_dir=str(tmp_path / "archive"),
        snapshots_dir=str(tmp_path / "snapshots"),
        llm=MagicMock(),
    )


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_import_pages_happy_path(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    files = [("acme.md", b"# Acme\nname: Acme Corp"), ("nike.md", b"# Nike\nname: Nike")]
    result = run(wm.import_pages("clients", files, {}))
    assert "clients/acme.md" in result["imported"]
    assert "clients/nike.md" in result["imported"]
    assert result["skipped"] == []
    assert result["errors"] == {}
    assert os.path.exists(os.path.join(wm.wiki_dir, "clients", "acme.md"))


def test_import_pages_skip_resolution(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    existing = os.path.join(wm.wiki_dir, "clients", "acme.md")
    with open(existing, "w") as f:
        f.write("original")
    files = [("acme.md", b"new content")]
    result = run(wm.import_pages("clients", files, {"acme.md": "skip"}))
    assert "acme.md" in result["skipped"]
    assert result["imported"] == []
    assert open(existing).read() == "original"


def test_import_pages_overwrite_resolution(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    existing = os.path.join(wm.wiki_dir, "clients", "acme.md")
    with open(existing, "w") as f:
        f.write("original")
    files = [("acme.md", b"new content")]
    result = run(wm.import_pages("clients", files, {"acme.md": "overwrite"}))
    assert "clients/acme.md" in result["imported"]
    assert open(existing, "rb").read() == b"new content"


def test_import_pages_rename_resolution(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    existing = os.path.join(wm.wiki_dir, "clients", "acme.md")
    with open(existing, "w") as f:
        f.write("original")
    files = [("acme.md", b"new content")]
    result = run(wm.import_pages("clients", files, {"acme.md": {"rename": "acme-v2.md"}}))
    assert "clients/acme-v2.md" in result["imported"]
    assert open(existing).read() == "original"


def test_import_pages_rename_conflict_error(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    for name in ("acme.md", "acme-v2.md"):
        with open(os.path.join(wm.wiki_dir, "clients", name), "w") as f:
            f.write("existing")
    files = [("acme.md", b"new content")]
    result = run(wm.import_pages("clients", files, {"acme.md": {"rename": "acme-v2.md"}}))
    assert "acme.md" in result["errors"]
    assert result["imported"] == []


def test_import_pages_missing_folder_raises(wm):
    files = [("acme.md", b"content")]
    with pytest.raises(FileNotFoundError):
        run(wm.import_pages("nonexistent", files, {}))


def test_import_pages_rebuilds_search_index(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    files = [("acme.md", b"---\nname: Acme\n---\n# Acme")]
    with patch.object(wm, "_rebuild_search_index") as mock_rebuild:
        run(wm.import_pages("clients", files, {}))
    mock_rebuild.assert_called_once()


def test_import_pages_no_rebuild_when_all_skipped(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    files = [("acme.md", b"content")]
    with patch.object(wm, "_rebuild_search_index") as mock_rebuild:
        run(wm.import_pages("clients", files, {"acme.md": "skip"}))
    mock_rebuild.assert_not_called()


import io
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, mock_env):
    # Create directories
    wiki_dir = str(tmp_path / "wiki")
    sources_dir = str(tmp_path / "sources")
    archive_dir = str(tmp_path / "archive")
    snapshots_dir = str(tmp_path / "snapshots")
    os.makedirs(os.path.join(wiki_dir, "clients"), exist_ok=True)
    os.makedirs(sources_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(snapshots_dir, exist_ok=True)

    # Import routes and set up wiki_manager
    from api import routes as r
    from agent.wiki_manager import WikiManager

    # Create and set wiki manager
    wm = WikiManager(
        sources_dir=sources_dir,
        wiki_dir=wiki_dir,
        archive_dir=archive_dir,
        snapshots_dir=snapshots_dir,
        llm=None,
    )
    r.set_wiki_manager(wm)

    # Create a fresh app with just the router
    app = FastAPI()
    app.include_router(r.router, prefix="/api")
    return TestClient(app)


def test_route_import_success(client):
    file_content = b"# Acme\nname: Acme Corp"
    response = client.post(
        "/api/wiki/import",
        data={"folder": "clients", "conflict_resolutions": "{}"},
        files=[("files", ("acme.md", io.BytesIO(file_content), "text/markdown"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert "clients/acme.md" in data["imported"]


def test_route_import_folder_not_found(client):
    response = client.post(
        "/api/wiki/import",
        data={"folder": "nonexistent", "conflict_resolutions": "{}"},
        files=[("files", ("acme.md", io.BytesIO(b"content"), "text/markdown"))],
    )
    assert response.status_code == 404


def test_route_import_non_md_file_rejected(client):
    response = client.post(
        "/api/wiki/import",
        data={"folder": "clients", "conflict_resolutions": "{}"},
        files=[("files", ("report.pdf", io.BytesIO(b"content"), "application/pdf"))],
    )
    assert response.status_code == 400


def test_route_import_invalid_resolutions_json(client):
    response = client.post(
        "/api/wiki/import",
        data={"folder": "clients", "conflict_resolutions": "not-json"},
        files=[("files", ("acme.md", io.BytesIO(b"content"), "text/markdown"))],
    )
    assert response.status_code == 400
