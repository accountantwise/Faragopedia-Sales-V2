import io
import json
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def dirs(tmp_path):
    schema_dir = tmp_path / "schema"
    wiki_dir = tmp_path / "wiki"
    sources_dir = tmp_path / "sources"
    archive_dir = tmp_path / "archive"
    snapshots_dir = tmp_path / "snapshots"

    for d in [schema_dir, wiki_dir, sources_dir, archive_dir, snapshots_dir]:
        d.mkdir()

    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "SCHEMA_TEMPLATE.md").write_text("# Template")
    (schema_dir / "company_profile.md").write_text("Acme Corp")
    (schema_dir / "wiki_config.json").write_text(json.dumps({
        "setup_complete": True,
        "wiki_name": "TestWiki",
        "org_name": "Acme",
        "org_description": "A company",
        "entity_types": [
            {"folder_name": "clients", "display_name": "Clients", "description": "Client orgs",
             "singular": "Client", "fields": [], "sections": ["Overview"]},
        ],
    }))

    clients_dir = wiki_dir / "clients"
    clients_dir.mkdir()
    (clients_dir / "_type.yaml").write_text("name: clients\n")
    (clients_dir / "acme.md").write_text("# Acme\n")
    (wiki_dir / "index.md").write_text("# Index\n")
    (wiki_dir / "log.md").write_text("# Log\n")
    (wiki_dir / "search-index.json").write_text("{}")

    metadata = {"doc.pdf": {"ingested": True, "ingested_at": "2026-01-01 00:00:00", "tags": []}}
    (sources_dir / ".metadata.json").write_text(json.dumps(metadata))
    (sources_dir / "doc.pdf").write_bytes(b"PDF content")
    (snapshots_dir / "20260101-000000.zip").write_bytes(b"snapshot data")

    return tmp_path


def _make_client(dirs):
    import backend.api.export_routes as er
    er.WIKI_DIR = str(dirs / "wiki")
    er.SOURCES_DIR = str(dirs / "sources")
    er.ARCHIVE_DIR = str(dirs / "archive")
    er.SNAPSHOTS_DIR = str(dirs / "snapshots")
    er.SCHEMA_DIR = str(dirs / "schema")

    app = FastAPI()
    app.include_router(er.export_router)
    return TestClient(app)


# ── Full export ────────────────────────────────────────────────────────────────

def test_full_export_returns_zip(dirs):
    r = _make_client(dirs).get("/bundle/full")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "faragopedia-full-" in r.headers["content-disposition"]


def test_full_export_manifest(dirs):
    r = _make_client(dirs).get("/bundle/full")
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        m = json.loads(zf.read("manifest.json"))
    assert m["version"] == 1
    assert m["type"] == "full"
    assert "exported_at" in m


def test_full_export_includes_all_directories(dirs):
    r = _make_client(dirs).get("/bundle/full")
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = set(zf.namelist())
    assert "schema/SCHEMA.md" in names
    assert "schema/wiki_config.json" in names
    assert "wiki/clients/_type.yaml" in names
    assert "wiki/clients/acme.md" in names
    assert "wiki/index.md" in names
    assert "sources/doc.pdf" in names
    assert "sources/.metadata.json" in names
    assert "snapshots/20260101-000000.zip" in names


# ── Template export ────────────────────────────────────────────────────────────

def test_template_export_returns_zip(dirs):
    r = _make_client(dirs).get("/bundle/template")
    assert r.status_code == 200
    assert "faragopedia-template-" in r.headers["content-disposition"]


def test_template_export_manifest(dirs):
    r = _make_client(dirs).get("/bundle/template")
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        m = json.loads(zf.read("manifest.json"))
    assert m["version"] == 1
    assert m["type"] == "template"


def test_template_export_structure_only(dirs):
    r = _make_client(dirs).get("/bundle/template")
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = set(zf.namelist())
    # Schema included in full
    assert "schema/SCHEMA.md" in names
    assert "schema/wiki_config.json" in names
    # Entity type structure included
    assert "wiki/clients/_type.yaml" in names
    # Page content excluded
    assert "wiki/clients/acme.md" not in names
    assert "wiki/index.md" not in names
    assert "wiki/search-index.json" not in names
    # Sources, archive, snapshots excluded
    assert "sources/doc.pdf" not in names
    assert "snapshots/20260101-000000.zip" not in names
