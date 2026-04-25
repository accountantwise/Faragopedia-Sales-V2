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


def test_rename_workspace_updates_name(ws_env):
    wm.update_workspace_name("ws-b", "Renamed B")
    registry = json.loads((ws_env / "registry.json").read_text())
    ws_b = next(ws for ws in registry["workspaces"] if ws["id"] == "ws-b")
    assert ws_b["name"] == "Renamed B"


def test_rename_active_workspace_updates_name(ws_env):
    """Renaming the active workspace is allowed."""
    wm.update_workspace_name("ws-a", "Renamed A")
    registry = json.loads((ws_env / "registry.json").read_text())
    ws_a = next(ws for ws in registry["workspaces"] if ws["id"] == "ws-a")
    assert ws_a["name"] == "Renamed A"


def test_rename_nonexistent_raises(ws_env):
    with pytest.raises(ValueError, match="not found"):
        wm.update_workspace_name("no-such", "Whatever")
