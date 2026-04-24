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
