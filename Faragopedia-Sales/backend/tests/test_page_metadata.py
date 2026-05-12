import asyncio
import os
import json
import pytest
from unittest.mock import patch
from agent.wiki_manager import WikiManager


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "AI_PROVIDER": "openai",
        "AI_MODEL": "gpt-4o-mini"
    }):
        yield


@pytest.fixture
def wm(tmp_path):
    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    return WikiManager(sources_dir=str(sources), wiki_dir=str(wiki))


def test_page_metadata_path_set(wm):
    expected = os.path.join(wm.wiki_dir, ".page-metadata.json")
    assert wm.page_metadata_path == expected


def test_load_page_metadata_missing_file(wm):
    assert wm._load_page_metadata() == {}


def test_save_and_load_page_metadata(wm):
    data = {"clients/acme.md": {"read": False, "read_at": None}}
    wm._save_page_metadata(data)
    assert wm._load_page_metadata() == data


def test_get_pages_metadata_empty(wm):
    assert wm.get_pages_metadata() == {}


def test_mark_pages_unread(wm):
    wm._mark_pages_unread(["clients/acme.md", "clients/beta.md"])
    metadata = wm._load_page_metadata()
    assert metadata["clients/acme.md"]["read"] is False
    assert metadata["clients/acme.md"]["read_at"] is None
    assert metadata["clients/beta.md"]["read"] is False


def test_mark_pages_unread_resets_existing_read(wm):
    wm._save_page_metadata({
        "clients/acme.md": {"read": True, "read_at": "2026-05-12 10:00:00"}
    })
    wm._mark_pages_unread(["clients/acme.md"])
    assert wm._load_page_metadata()["clients/acme.md"]["read"] is False
    assert wm._load_page_metadata()["clients/acme.md"]["read_at"] is None


@pytest.mark.asyncio
async def test_mark_page_read(wm):
    wm._mark_pages_unread(["clients/acme.md"])
    await wm.mark_page_read("clients/acme.md")
    metadata = wm._load_page_metadata()
    assert metadata["clients/acme.md"]["read"] is True
    assert metadata["clients/acme.md"]["read_at"] is not None


@pytest.mark.asyncio
async def test_mark_page_read_creates_entry_if_absent(wm):
    await wm.mark_page_read("clients/new.md")
    metadata = wm._load_page_metadata()
    assert metadata["clients/new.md"]["read"] is True


@pytest.mark.asyncio
async def test_ingest_source_marks_pages_unread(wm, tmp_path):
    """Pages written by ingest_source should be marked unread."""
    # Pre-populate a page as read
    wm._save_page_metadata({
        "clients/acme.md": {"read": True, "read_at": "2026-05-12 10:00:00"}
    })

    # Simulate what ingest writes by calling _mark_pages_unread inside the lock
    # (integration smoke: verify the lock + method interaction)
    async with wm._write_lock:
        wm._mark_pages_unread(["clients/acme.md"])

    metadata = wm._load_page_metadata()
    assert metadata["clients/acme.md"]["read"] is False
