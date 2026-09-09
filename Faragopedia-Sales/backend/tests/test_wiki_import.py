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
    # asyncio.run, not get_event_loop().run_until_complete: from Python 3.12 the
    # latter raises "no current event loop" outside a running loop rather than
    # creating one, which errored every test in this module on 3.14.
    return asyncio.run(coro)


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


# --- index.md, log.md and the write lock -------------------------------------------
# import_pages previously rebuilt only the search index, so a bulk import left pages
# searchable but absent from index.md and unrecorded in log.md — unlike every other
# write path on WikiManager.


def _register_entity_type(wiki_dir, folder, singular):
    """update_index only lists folders that are registered entity types, i.e. carry a
    _type.yaml. POST /folders always writes one, so a folder created through the API is
    indexed; a bare mkdir is not."""
    import yaml
    os.makedirs(os.path.join(wiki_dir, folder), exist_ok=True)
    with open(os.path.join(wiki_dir, folder, "_type.yaml"), "w", encoding="utf-8") as f:
        yaml.dump({
            "name": folder.title(),
            "description": "",
            "singular": singular,
            "fields": [{"name": "name", "type": "string", "required": True}],
            "sections": ["Overview"],
        }, f)


def test_import_pages_into_unregistered_folder_is_absent_from_index(wm, tmp_path):
    """A folder with no _type.yaml is not an entity type, so its pages never reach
    index.md however many are imported. They are still searchable and still logged."""
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "loose"))
    run(wm.import_pages("loose", [("acme.md", b"# Acme\n")], {}))

    index = open(os.path.join(wm.wiki_dir, "index.md"), encoding="utf-8").read()
    assert "[[loose/acme]]" not in index
    assert "import_pages" in open(os.path.join(wm.wiki_dir, "log.md"), encoding="utf-8").read()


def test_import_pages_updates_index_and_log(wm, tmp_path):
    _register_entity_type(str(tmp_path / "wiki"), "clients", "client")
    files = [("acme.md", b"---\ntype: client\nname: Acme\n---\n# Acme\n")]
    run(wm.import_pages("clients", files, {}))

    # index.md lists pages as wikilinks, extension stripped.
    index = open(os.path.join(wm.wiki_dir, "index.md"), encoding="utf-8").read()
    assert "[[clients/acme]]" in index

    log = open(os.path.join(wm.wiki_dir, "log.md"), encoding="utf-8").read()
    assert "import_pages" in log
    assert "Imported 1 page(s) into 'clients'" in log


def test_import_pages_leaves_index_and_log_alone_when_all_skipped(wm, tmp_path):
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    with open(os.path.join(wm.wiki_dir, "clients", "acme.md"), "w") as f:
        f.write("original")
    run(wm.import_pages("clients", [("acme.md", b"new")], {"acme.md": "skip"}))

    assert not os.path.exists(os.path.join(wm.wiki_dir, "log.md"))


def test_import_pages_holds_the_write_lock_while_writing(wm, tmp_path):
    """The lock must be held across the batch, not per file — a lint or rename
    interleaving mid-batch would index a half-written set."""
    os.makedirs(os.path.join(str(tmp_path / "wiki"), "clients"))
    locked_during_write = []

    real_open = open

    def spy_open(path, *a, **k):
        if str(path).endswith("acme.md") and "b" in (a[0] if a else k.get("mode", "")):
            locked_during_write.append(wm._write_lock.locked())
        return real_open(path, *a, **k)

    with patch("agent.wiki_manager.open", spy_open, create=True):
        run(wm.import_pages("clients", [("acme.md", b"content")], {}))

    assert locked_during_write == [True]


def test_route_import_passes_fields_through_to_create_folder(client):
    """POST /folders forwards an explicit schema; the folder is then importable."""
    response = client.post("/api/folders", json={
        "name": "jobs",
        "display_name": "Jobs",
        "description": "Production jobs",
        "singular": "job",
        "fields": [
            {"name": "type", "type": "string", "default": "job"},
            {"name": "name", "type": "string", "required": True},
            {"name": "job_reference_number", "type": "string"},
        ],
        "sections": ["Overview", "Shoot Days"],
    })
    assert response.status_code == 200, response.text

    imported = client.post(
        "/api/wiki/import",
        data={"folder": "jobs", "conflict_resolutions": "{}"},
        files=[("files", ("job-526.md", io.BytesIO(b"---\ntype: job\n---\n# 526\n"), "text/markdown"))],
    )
    assert imported.status_code == 200, imported.text
    assert "jobs/job-526.md" in imported.json()["imported"]


def test_route_folders_rejects_enum_without_values(client):
    response = client.post("/api/folders", json={
        "name": "jobs",
        "display_name": "Jobs",
        "fields": [{"name": "category", "type": "enum"}],
    })
    assert response.status_code == 422
    assert "values list" in response.json()["detail"]


def test_route_folders_still_accepts_the_ui_payload(client):
    """The New Folder dialog sends only these three keys."""
    response = client.post("/api/folders", json={
        "name": "stylists",
        "display_name": "Stylists",
        "description": "Hair and makeup",
    })
    assert response.status_code == 200, response.text
