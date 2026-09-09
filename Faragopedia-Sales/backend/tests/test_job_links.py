import json
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.job_links import host_is_allowed


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-4")

    from agent.wiki_manager import WikiManager
    from api import routes as r
    from api.job_links import job_links_router

    for sub in ("wiki", "sources", "archive", "snapshots"):
        os.makedirs(tmp_path / sub, exist_ok=True)
    wm = WikiManager(
        sources_dir=str(tmp_path / "sources"),
        wiki_dir=str(tmp_path / "wiki"),
        archive_dir=str(tmp_path / "archive"),
        snapshots_dir=str(tmp_path / "snapshots"),
        llm=None,
    )
    r.set_wiki_manager(wm)
    app = FastAPI()
    app.include_router(job_links_router, prefix="/api")
    c = TestClient(app, follow_redirects=False)
    c.wiki_dir = str(tmp_path / "wiki")
    return c


DROPBOX = "https://www.dropbox.com/home/Team%20Folder/526_MCQUEEN"
DRIVE = "https://drive.google.com/drive/folders/0ABCdef"


# --- host allowlist ----------------------------------------------------------------

@pytest.mark.parametrize("url", [
    DROPBOX,
    DRIVE,
    "https://dropbox.com/home/x",
    "https://docs.google.com/spreadsheets/d/abc",
])
def test_host_is_allowed_accepts_storage_hosts(url):
    assert host_is_allowed(url)


@pytest.mark.parametrize("url", [
    "https://evil.test/phish",
    # The classic suffix attack: allowed name as a prefix of another domain.
    "https://dropbox.com.evil.test/x",
    "https://notdropbox.com/x",
    "",
    "not-a-url",
    "javascript:alert(1)",
])
def test_host_is_allowed_rejects_everything_else(url):
    assert not host_is_allowed(url)


# --- resolve -----------------------------------------------------------------------

def _write_table(client, links):
    meta = os.path.join(client.wiki_dir, "_meta")
    os.makedirs(meta, exist_ok=True)
    with open(os.path.join(meta, "job-links.json"), "w", encoding="utf-8") as f:
        json.dump({"links": links}, f)


def test_resolve_redirects_to_the_recorded_url(client):
    _write_table(client, {"job-526": {"url": DROPBOX, "provider": "dropbox"}})
    res = client.get("/api/job/job-526")
    assert res.status_code == 302
    assert res.headers["location"] == DROPBOX


def test_resolve_unknown_key_is_404_not_a_redirect(client):
    """The key is a job number and therefore guessable, so a miss must not leak or
    forward anywhere."""
    _write_table(client, {"job-526": {"url": DROPBOX}})
    res = client.get("/api/job/job-999")
    assert res.status_code == 404
    assert "location" not in res.headers


def test_resolve_with_no_table_at_all_is_404(client):
    res = client.get("/api/job/job-526")
    assert res.status_code == 404


def test_resolve_refuses_a_tampered_destination(client):
    """A stored row pointing off-site is a data-integrity problem: refuse rather than
    forward, so a corrupted table cannot be used to bounce people anywhere."""
    _write_table(client, {"job-526": {"url": "https://evil.test/phish"}})
    res = client.get("/api/job/job-526")
    assert res.status_code == 502
    assert "location" not in res.headers


def test_resolve_ignores_a_url_supplied_as_a_query_parameter(client):
    """There is no open-redirect surface: the table is the only authority."""
    _write_table(client, {"job-526": {"url": DROPBOX}})
    res = client.get("/api/job/job-526", params={"url": "https://evil.test/phish"})
    assert res.status_code == 302
    assert res.headers["location"] == DROPBOX


def test_resolve_entry_without_url_is_404(client):
    _write_table(client, {"job-526": {"provider": "dropbox"}})
    assert client.get("/api/job/job-526").status_code == 404


# --- replace -----------------------------------------------------------------------

def test_put_replaces_the_table_and_resolves(client):
    res = client.put("/api/job-links", json={"links": {
        "job-526": {"url": DROPBOX, "provider": "dropbox", "id": "id:abc"},
        "job-534": {"url": DRIVE, "provider": "drive"},
    }})
    assert res.status_code == 200
    assert res.json()["count"] == 2
    assert client.get("/api/job/job-534").headers["location"] == DRIVE


def test_put_is_a_whole_table_replacement(client):
    """Generated from the archive each run, so a partial update would let it drift."""
    client.put("/api/job-links", json={"links": {"job-526": {"url": DROPBOX}}})
    client.put("/api/job-links", json={"links": {"job-534": {"url": DRIVE}}})
    assert client.get("/api/job/job-526").status_code == 404
    assert client.get("/api/job/job-534").status_code == 302


def test_put_rejects_a_disallowed_host_at_write_time(client):
    """Validated on the way in as well as on the way out, so the error is visible while
    somebody is still watching."""
    res = client.put("/api/job-links", json={"links": {
        "job-526": {"url": "https://evil.test/phish"},
    }})
    assert res.status_code == 422
    assert "approved storage host" in res.json()["detail"]


@pytest.mark.parametrize("payload,expected", [
    ({}, "links must be an object"),
    ({"links": []}, "links must be an object"),
    ({"links": {"job-526": "https://www.dropbox.com/x"}}, "must be an object"),
    ({"links": {"job-526": {}}}, "missing url"),
])
def test_put_rejects_malformed_payloads(client, payload, expected):
    res = client.put("/api/job-links", json=payload)
    assert res.status_code == 422
    assert expected in res.json()["detail"]


def test_get_job_links_reads_the_table_back(client):
    client.put("/api/job-links", json={"links": {"job-526": {"url": DROPBOX}}})
    body = client.get("/api/job-links").json()
    assert body["count"] == 1
    assert body["links"]["job-526"]["url"] == DROPBOX
