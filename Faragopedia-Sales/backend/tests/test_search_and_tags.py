import json
import os
import pytest
import yaml
from unittest.mock import patch
from agent.wiki_manager import WikiManager


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "AI_PROVIDER": "openai",
        "AI_MODEL": "gpt-4o-mini",
    }):
        yield


@pytest.fixture
def wiki_env(tmp_path):
    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    archive = tmp_path / "archive"
    sources.mkdir()
    wiki.mkdir()
    # Create a clients entity folder with _type.yaml
    clients = wiki / "clients"
    clients.mkdir()
    (clients / "_type.yaml").write_text(
        yaml.dump({"name": "Clients", "singular": "client", "fields": [], "sections": []})
    )
    return str(sources), str(wiki), str(archive)


def make_manager(wiki_env):
    sources, wiki, archive = wiki_env
    return WikiManager(sources_dir=sources, wiki_dir=wiki, archive_dir=archive)


def write_page(wiki_dir, rel_path, content):
    full = os.path.join(wiki_dir, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


# ── Parsing helpers ───────────────────────────────────────────────────────────

def test_parse_frontmatter_with_tags(wiki_env):
    manager = make_manager(wiki_env)
    content = "---\nname: Acme Corp\ntags:\n- wedding\n- VIP\n---\n\n# Acme Corp\n\nBody."
    fm, body = manager._parse_frontmatter(content)
    assert fm["name"] == "Acme Corp"
    assert fm["tags"] == ["wedding", "VIP"]
    assert "Body." in body


def test_parse_frontmatter_no_yaml(wiki_env):
    manager = make_manager(wiki_env)
    content = "# Just a heading\n\nNo frontmatter."
    fm, body = manager._parse_frontmatter(content)
    assert fm == {}
    assert "Just a heading" in body


def test_render_frontmatter_roundtrip(wiki_env):
    manager = make_manager(wiki_env)
    content = "---\nname: Test\ntags:\n- foo\n---\n\nBody text."
    fm, body = manager._parse_frontmatter(content)
    rendered = manager._render_frontmatter(fm, body)
    fm2, body2 = manager._parse_frontmatter(rendered)
    assert fm2["name"] == "Test"
    assert fm2["tags"] == ["foo"]
    assert "Body text." in body2


def test_strip_markdown(wiki_env):
    manager = make_manager(wiki_env)
    text = "## Header\n\n**bold** and [[clients/foo]] and *italic* and [link](url)"
    result = manager._strip_markdown(text)
    assert "##" not in result
    assert "**" not in result
    assert "[[" not in result
    assert "Header" in result
    assert "bold" in result


# ── Search index builder ──────────────────────────────────────────────────────

def test_rebuild_search_index_creates_file(wiki_env):
    sources, wiki, archive = wiki_env
    manager = make_manager(wiki_env)
    write_page(wiki, "clients/acme-corp.md",
               "---\ntype: client\nname: Acme Corp\ntags:\n- wedding\n---\n\n# Acme Corp\n\nContent here.")

    manager._rebuild_search_index()

    index_path = os.path.join(wiki, "search-index.json")
    assert os.path.exists(index_path)
    with open(index_path) as f:
        index = json.load(f)
    assert len(index["pages"]) == 1
    assert index["pages"][0]["path"] == "clients/acme-corp.md"
    assert index["pages"][0]["title"] == "Acme Corp"
    assert index["pages"][0]["tags"] == ["wedding"]
    assert "Content here" in index["pages"][0]["content_preview"]


def test_rebuild_search_index_includes_sources(wiki_env):
    sources, wiki, archive = wiki_env
    manager = make_manager(wiki_env)
    src_file = os.path.join(sources, "brief.pdf")
    with open(src_file, "w") as f:
        f.write("dummy")
    # Manually write metadata with tags
    meta = {"brief.pdf": {"ingested": True, "ingested_at": "2026-01-01", "tags": ["brief"]}}
    meta_path = os.path.join(sources, ".metadata.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f)

    manager._rebuild_search_index()

    with open(os.path.join(wiki, "search-index.json")) as f:
        index = json.load(f)
    src_entry = next((s for s in index["sources"] if s["filename"] == "brief.pdf"), None)
    assert src_entry is not None
    assert src_entry["tags"] == ["brief"]


def test_init_creates_index_if_missing(wiki_env):
    sources, wiki, archive = wiki_env
    write_page(wiki, "clients/test.md",
               "---\nname: Test\ntags: []\n---\n\n# Test\n\nHello.")
    # Index should not exist yet
    assert not os.path.exists(os.path.join(wiki, "search-index.json"))
    make_manager(wiki_env)
    assert os.path.exists(os.path.join(wiki, "search-index.json"))
