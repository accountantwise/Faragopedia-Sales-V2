import json
import os
import pytest
import agent.workspace_manager as wm


@pytest.fixture
def ws_env(tmp_path, monkeypatch):
    monkeypatch.setattr(wm, "REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setattr(wm, "WORKSPACES_BASE", str(tmp_path))
    monkeypatch.setattr(wm, "_active_workspace_id", "ws-a")

    for ws_id in ("ws-a", "ws-b"):
        for sub in ("wiki", "sources", "archive", "snapshots", "schema"):
            os.makedirs(tmp_path / ws_id / sub, exist_ok=True)

    registry = {
        "active_workspace_id": "ws-a",
        "workspaces": [
            {"id": "ws-a", "name": "Workspace A", "created_at": "2026-01-01T00:00:00"},
            {"id": "ws-b", "name": "Workspace B", "created_at": "2026-01-01T00:00:00"},
        ],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry))
    return tmp_path


def test_archive_workspace_sets_flag(ws_env):
    result = wm.archive_workspace("ws-b")
    assert result["archived"] is True
    registry = json.loads((ws_env / "registry.json").read_text())
    ws_b = next(ws for ws in registry["workspaces"] if ws["id"] == "ws-b")
    assert ws_b["archived"] is True


def test_archive_active_workspace_raises(ws_env):
    with pytest.raises(ValueError, match="active"):
        wm.archive_workspace("ws-a")


def test_archive_nonexistent_raises(ws_env):
    with pytest.raises(ValueError, match="not found"):
        wm.archive_workspace("no-such-ws")


def test_unarchive_workspace_clears_flag(ws_env):
    # Manually archive first
    reg = json.loads((ws_env / "registry.json").read_text())
    for ws in reg["workspaces"]:
        if ws["id"] == "ws-b":
            ws["archived"] = True
    (ws_env / "registry.json").write_text(json.dumps(reg))

    result = wm.unarchive_workspace("ws-b")
    assert result["archived"] is False
    registry = json.loads((ws_env / "registry.json").read_text())
    ws_b = next(ws for ws in registry["workspaces"] if ws["id"] == "ws-b")
    assert ws_b["archived"] is False


def test_unarchive_nonexistent_raises(ws_env):
    with pytest.raises(ValueError, match="not found"):
        wm.unarchive_workspace("no-such-ws")


@pytest.fixture
def ws_with_content(tmp_path, monkeypatch):
    """ws_env with content files in ws-a for copy testing."""
    monkeypatch.setattr(wm, "REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setattr(wm, "WORKSPACES_BASE", str(tmp_path))
    monkeypatch.setattr(wm, "_active_workspace_id", "ws-a")
    monkeypatch.setattr(wm, "_active_dirs", {
        "wiki_dir":      str(tmp_path / "ws-a" / "wiki"),
        "sources_dir":   str(tmp_path / "ws-a" / "sources"),
        "archive_dir":   str(tmp_path / "ws-a" / "archive"),
        "snapshots_dir": str(tmp_path / "ws-a" / "snapshots"),
        "schema_dir":    str(tmp_path / "ws-a" / "schema"),
    })

    # Create ws-a with content
    schema = tmp_path / "ws-a" / "schema"
    wiki = tmp_path / "ws-a" / "wiki"
    for sub in ("wiki", "sources", "archive", "snapshots", "schema"):
        os.makedirs(tmp_path / "ws-a" / sub, exist_ok=True)

    (schema / "wiki_config.json").write_text(json.dumps({"setup_complete": True, "wiki_name": "A"}))
    (schema / "SCHEMA.md").write_text("# Schema A")

    clients = wiki / "clients"
    clients.mkdir()
    (clients / "_type.yaml").write_text("name: Clients\n")
    (clients / "_template.md").write_text("# Template\n")
    (clients / "acme.md").write_text("# Acme\n")
    (wiki / "index.md").write_text("# Index\n")

    registry = {
        "active_workspace_id": "ws-a",
        "workspaces": [
            {"id": "ws-a", "name": "Workspace A", "created_at": "2026-01-01T00:00:00"},
        ],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry))
    return tmp_path


def test_duplicate_full_copies_all_content(ws_with_content):
    result = wm.duplicate_workspace("ws-a", "Copy of A", "full")
    new_id = result["id"]
    assert result["setup_required"] is False

    new_wiki = ws_with_content / new_id / "wiki"
    assert (new_wiki / "clients" / "_type.yaml").exists()
    assert (new_wiki / "clients" / "acme.md").exists()
    assert (new_wiki / "index.md").exists()

    new_schema = ws_with_content / new_id / "schema"
    assert (new_schema / "wiki_config.json").exists()
    assert (new_schema / "SCHEMA.md").exists()


def test_duplicate_full_registers_new_workspace(ws_with_content):
    result = wm.duplicate_workspace("ws-a", "Copy of A", "full")
    registry = json.loads((ws_with_content / "registry.json").read_text())
    ids = [ws["id"] for ws in registry["workspaces"]]
    assert result["id"] in ids
    new_entry = next(ws for ws in registry["workspaces"] if ws["id"] == result["id"])
    assert new_entry.get("archived") is False


def test_duplicate_template_copies_only_structure(ws_with_content):
    result = wm.duplicate_workspace("ws-a", "Template Copy", "template")
    new_id = result["id"]
    assert result["setup_required"] is True

    new_wiki = ws_with_content / new_id / "wiki"
    assert (new_wiki / "clients" / "_type.yaml").exists()
    assert (new_wiki / "clients" / "_template.md").exists()
    assert not (new_wiki / "clients" / "acme.md").exists()

    new_schema = ws_with_content / new_id / "schema"
    assert (new_schema / "SCHEMA.md").exists()
    assert not (new_schema / "wiki_config.json").exists()


def test_duplicate_nonexistent_raises(ws_with_content):
    with pytest.raises(ValueError, match="not found"):
        wm.duplicate_workspace("no-such", "Name", "full")


def test_duplicate_invalid_mode_raises(ws_with_content):
    with pytest.raises(ValueError, match="Invalid mode"):
        wm.duplicate_workspace("ws-a", "Name", "invalid")


def test_duplicate_slug_uniqueness(ws_with_content):
    result1 = wm.duplicate_workspace("ws-a", "Copy", "full")
    # Re-patch active to the original after first duplicate switched it
    import agent.workspace_manager as wm2
    wm2._active_workspace_id = result1["id"]
    result2 = wm.duplicate_workspace("ws-a", "Copy", "full")
    assert result1["id"] != result2["id"]
