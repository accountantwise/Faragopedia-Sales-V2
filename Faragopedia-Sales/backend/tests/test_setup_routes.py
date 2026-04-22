import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_tmp = tempfile.mkdtemp()
_schema_dir = os.path.join(_tmp, "schema")
_wiki_dir = os.path.join(_tmp, "wiki")
os.makedirs(_schema_dir, exist_ok=True)
os.makedirs(_wiki_dir, exist_ok=True)

# Patch module-level path constants BEFORE importing main
import api.setup_routes as sr
import api.routes as ar
sr.SCHEMA_DIR = _schema_dir
sr.WIKI_DIR = _wiki_dir
ar.WIKI_DIR = _wiki_dir

from main import app  # noqa: E402

client = TestClient(app)


def _clear_state():
    config = os.path.join(_schema_dir, "wiki_config.json")
    if os.path.exists(config):
        os.remove(config)
    import api.routes
    api.routes.set_wiki_manager(None)


def test_setup_status_required_when_no_config():
    _clear_state()
    r = client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json()["setup_required"] is True


def test_setup_status_not_required_when_config_present():
    _clear_state()
    config = {"wiki_name": "TestWiki", "org_name": "Test Org", "setup_complete": True}
    with open(os.path.join(_schema_dir, "wiki_config.json"), "w") as f:
        json.dump(config, f)
    r = client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json()["setup_required"] is False
    assert r.json()["wiki_name"] == "TestWiki"


def test_setup_config_returns_404_when_missing():
    _clear_state()
    r = client.get("/api/setup/config")
    assert r.status_code == 404


def test_wiki_routes_return_503_when_not_setup():
    _clear_state()
    r = client.get("/api/pages")
    assert r.status_code == 503


def test_setup_clear_returns_existing_folders():
    _clear_state()
    folder = os.path.join(_wiki_dir, "clients")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "_type.yaml"), "w") as f:
        f.write("name: Clients\n")
    r = client.post("/api/setup/clear")
    assert r.status_code == 200
    assert "clients" in r.json()["existing_folders"]


def test_delete_setup_folder():
    folder = os.path.join(_wiki_dir, "to-delete")
    os.makedirs(folder, exist_ok=True)
    r = client.delete("/api/setup/folder/to-delete")
    assert r.status_code == 200
    assert not os.path.exists(folder)


def test_delete_setup_folder_invalid_name():
    r = client.delete("/api/setup/folder/../etc")
    assert r.status_code in (400, 404)
