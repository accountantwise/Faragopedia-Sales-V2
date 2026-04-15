from unittest.mock import MagicMock, patch
import pytest
import os
import shutil
from agent.wiki_manager import WikiManager

@pytest.fixture
def wiki_manager(tmp_path):
    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    with patch('agent.wiki_manager.ChatOpenAI'):
        return WikiManager(sources_dir=str(sources), wiki_dir=str(wiki))

def test_health_check_empty(wiki_manager):
    report = wiki_manager.health_check()
    assert report["orphan_pages"] == []
    assert report["missing_pages"] == []

def test_health_check_with_issues(wiki_manager):
    # Create orphan page
    orphan_path = os.path.join(wiki_manager.wiki_dir, "orphan.md")
    with open(orphan_path, "w") as f:
        f.write("# Orphan\nNo links here.")
    
    # Create index with missing page link
    index_path = os.path.join(wiki_manager.wiki_dir, "index.md")
    with open(index_path, "w") as f:
        f.write("# Index\n- [[missing]]: Missing page\n- [[orphan]]: Existing link")
        
    report = wiki_manager.health_check()
    # orphan is linked in index, so it shouldn't be an orphan if index counts as inbound
    # The requirement says "orphan pages (no inbound links)"
    # Usually index.md links to everything, so we should check other pages or exclude index.md from inbound link source?
    # Let's say index.md is the entry point, so anything NOT in index.md is an orphan?
    # Or anything NOT linked from ANY other page.
    
    # If I only have orphan.md and index.md, and index.md links to orphan.md.
    # If I have another_page.md and it's NOT linked from index.md AND not linked from orphan.md, it's an orphan.
    
    # Let's adjust the test to be more specific.
    with open(os.path.join(wiki_manager.wiki_dir, "real_orphan.md"), "w") as f:
        f.write("# Real Orphan\nNo one links to me.")
    
    report = wiki_manager.health_check()
    assert "real_orphan.md" in report["orphan_pages"]
    assert "missing" in report["missing_pages"]

def test_list_pages(wiki_manager):
    with open(os.path.join(wiki_manager.wiki_dir, "page1.md"), "w") as f:
        f.write("# Page 1")
    with open(os.path.join(wiki_manager.wiki_dir, "page2.md"), "w") as f:
        f.write("# Page 2")
    
    pages = wiki_manager.list_pages()
    assert "page1.md" in pages
    assert "page2.md" in pages
    assert "index.md" not in pages # Usually we might want to exclude index/log or keep them? 
    # Let's exclude index and log from the main list if they are special.
