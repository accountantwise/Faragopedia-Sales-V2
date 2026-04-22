import io
import json
import os
import zipfile
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def dirs(tmp_path):
    schema_dir = tmp_path / "schema"
    wiki_dir = tmp_path / "wiki"
    schema_dir.mkdir()
    wiki_dir.mkdir()

    (schema_dir / "SCHEMA.md").write_text("# Schema content")
    (schema_dir / "company_profile.md").write_text("# Org Profile")
    (schema_dir / "wiki_config.json").write_text(
        json.dumps({"wiki_name": "TestWiki", "org_name": "TestOrg", "setup_complete": True})
    )
    (wiki_dir / "index.md").write_text("# Index")
    (wiki_dir / "log.md").write_text("# Log")
    return str(schema_dir), str(wiki_dir)


def _client(schema_dir, wiki_dir):
    import importlib
    from api import export_routes
    importlib.reload(export_routes)
    export_routes.SCHEMA_DIR = schema_dir
    export_routes.WIKI_DIR = wiki_dir
    app = FastAPI()
    app.include_router(export_routes.export_router)
    return TestClient(app)


def test_bundle_returns_zip_with_all_files(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)

    response = client.get("/bundle")

    assert response.status_code == 200
    assert "application/zip" in response.headers["content-type"]
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = zf.namelist()
    assert "SCHEMA.md" in names
    assert "company_profile.md" in names
    assert "wiki_config.json" in names
    assert "index.md" in names
    assert "log.md" in names


def test_bundle_skips_missing_files(dirs):
    schema_dir, wiki_dir = dirs
    import os
    os.remove(os.path.join(wiki_dir, "log.md"))
    client = _client(schema_dir, wiki_dir)

    response = client.get("/bundle")

    assert response.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = zf.namelist()
    assert "log.md" not in names
    assert "index.md" in names


def _make_zip(include_schema=True, include_profile=True, include_config=True, config_data=None):
    if config_data is None:
        config_data = {
            "wiki_name": "ImportedWiki",
            "org_name": "ImportedOrg",
            "org_description": "An imported org",
            "entity_types": [
                {
                    "folder_name": "clients",
                    "display_name": "Clients",
                    "description": "Client orgs",
                    "singular": "client",
                    "fields": [{"name": "name", "type": "string", "required": True}],
                    "sections": ["Overview"],
                }
            ],
        }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if include_schema:
            zf.writestr("SCHEMA.md", "# Imported Schema")
        if include_profile:
            zf.writestr("company_profile.md", "# Imported Org")
        if include_config:
            zf.writestr("wiki_config.json", json.dumps(config_data))
    buf.seek(0)
    return buf.read()


def test_import_stages_files_and_returns_config(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)
    zip_bytes = _make_zip()

    response = client.post(
        "/import",
        files={"file": ("wiki-bundle.zip", zip_bytes, "application/zip")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["wiki_name"] == "ImportedWiki"
    assert data["org_name"] == "ImportedOrg"
    assert len(data["entity_types"]) == 1
    assert os.path.exists(os.path.join(schema_dir, "SCHEMA.md"))
    assert open(os.path.join(schema_dir, "SCHEMA.md")).read() == "# Imported Schema"
    assert os.path.exists(os.path.join(schema_dir, "company_profile.md"))
    # wiki_config.json must NOT be written by import (finalize does that)
    config_on_disk = json.loads(open(os.path.join(schema_dir, "wiki_config.json")).read())
    assert config_on_disk.get("wiki_name") != "ImportedWiki"


def test_import_rejects_invalid_zip(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)

    response = client.post(
        "/import",
        files={"file": ("bad.zip", b"not a zip", "application/zip")},
    )
    assert response.status_code == 422


def test_import_rejects_missing_schema(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)
    zip_bytes = _make_zip(include_schema=False)

    response = client.post(
        "/import",
        files={"file": ("bundle.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 422


def test_import_rejects_missing_config(dirs):
    schema_dir, wiki_dir = dirs
    client = _client(schema_dir, wiki_dir)
    zip_bytes = _make_zip(include_config=False)

    response = client.post(
        "/import",
        files={"file": ("bundle.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 422


def test_finalize_creates_folders_and_config(dirs):
    schema_dir, wiki_dir = dirs
    import os
    with open(os.path.join(schema_dir, "SCHEMA.md"), "w") as f:
        f.write("# Imported Schema")
    with open(os.path.join(schema_dir, "company_profile.md"), "w") as f:
        f.write("# Imported Org")

    client = _client(schema_dir, wiki_dir)
    payload = {
        "wiki_name": "ImportedWiki",
        "org_name": "ImportedOrg",
        "org_description": "An org",
        "entity_types": [
            {
                "folder_name": "clients",
                "display_name": "Clients",
                "description": "Client orgs",
                "singular": "client",
                "fields": [{"name": "name", "type": "string", "required": True}],
                "sections": ["Overview"],
            }
        ],
    }

    response = client.post("/import/finalize", json=payload)

    assert response.status_code == 200
    assert response.json()["success"] is True
    config_path = os.path.join(schema_dir, "wiki_config.json")
    assert os.path.exists(config_path)
    config = json.loads(open(config_path).read())
    assert config["setup_complete"] is True
    assert config["wiki_name"] == "ImportedWiki"
    assert os.path.isdir(os.path.join(wiki_dir, "clients"))
    assert os.path.exists(os.path.join(wiki_dir, "clients", "_type.yaml"))
    # Must NOT overwrite SCHEMA.md
    assert open(os.path.join(schema_dir, "SCHEMA.md")).read() == "# Imported Schema"
