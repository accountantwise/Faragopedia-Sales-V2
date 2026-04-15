import os
import pytest
import shutil
import asyncio
from agent.wiki_manager import WikiManager

@pytest.fixture
def temp_wiki(tmp_path):
    sources_dir = tmp_path / "sources"
    wiki_dir = tmp_path / "wiki"
    sources_dir.mkdir()
    wiki_dir.mkdir()
    
    # Create some dummy pages
    (wiki_dir / "Page_A.md").write_text("# Page A\n\nLinks to [[Page B]] and [[Page C]].", encoding="utf-8")
    (wiki_dir / "Page_B.md").write_text("# Page B\n\nLinks back to [[Page A]].", encoding="utf-8")
    (wiki_dir / "Page_C.md").write_text("# Page C\n\nNo links here.", encoding="utf-8")
    (wiki_dir / "Page_D.md").write_text("# Page D\n\nLinks to [[Page B]].", encoding="utf-8")
    
    # Mock LLM to avoid API key issues in tests that don't need it
    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    
    manager = WikiManager(sources_dir=str(sources_dir), wiki_dir=str(wiki_dir), llm=mock_llm)
    return manager, wiki_dir

def test_get_backlinks(temp_wiki):
    manager, wiki_dir = temp_wiki
    
    # Page B should have backlinks from Page A and Page D
    backlinks_b = manager.get_backlinks("Page_B.md")
    assert "Page_A.md" in backlinks_b
    assert "Page_D.md" in backlinks_b
    assert len(backlinks_b) == 2
    
    # Page A should have backlink from Page B
    backlinks_a = manager.get_backlinks("Page_A.md")
    assert "Page_B.md" in backlinks_a
    assert len(backlinks_a) == 1
    
    # Page C should have backlink from Page A
    backlinks_c = manager.get_backlinks("Page_C.md")
    assert "Page_A.md" in backlinks_c
    assert len(backlinks_c) == 1

@pytest.mark.asyncio
async def test_save_page_content(temp_wiki):
    manager, wiki_dir = temp_wiki
    
    new_content = "# Page C Updated\n\nNow it links to [[Page A]]."
    await manager.save_page_content("Page_C.md", new_content)
    
    # Verify content was saved
    with open(wiki_dir / "Page_C.md", "r", encoding="utf-8") as f:
        assert f.read() == new_content
    
    # Verify index was updated (indirectly by checking if Page C still exists in it)
    index_path = wiki_dir / "index.md"
    assert index_path.exists()
    
    # Verify log entry
    log_path = wiki_dir / "log.md"
    assert log_path.exists()
    with open(log_path, "r", encoding="utf-8") as f:
        assert "edit | Updated Page_C.md" in f.read()

def test_get_backlinks_with_markdown_links(temp_wiki):
    manager, wiki_dir = temp_wiki
    
    # Add a page with standard markdown link
    (wiki_dir / "Page_E.md").write_text("# Page E\n\n[Link to B](Page_B.md)", encoding="utf-8")
    
    backlinks_b = manager.get_backlinks("Page_B.md")
    assert "Page_E.md" in backlinks_b
    assert "Page_A.md" in backlinks_b
    assert "Page_D.md" in backlinks_b

@pytest.mark.asyncio
async def test_sources_features(temp_wiki):
    manager, _ = temp_wiki
    sources_dir = manager.sources_dir
    
    # 1. Test listing sources
    # Add some source files
    with open(os.path.join(sources_dir, "test1.txt"), "w", encoding="utf-8") as f:
        f.write("Hello from test1")
    with open(os.path.join(sources_dir, "test2.md"), "w", encoding="utf-8") as f:
        f.write("Hello from test2")
    
    sources = manager.list_sources()
    assert "test1.txt" in sources
    assert "test2.md" in sources
    assert len(sources) == 2
    
    # 2. Test reading source content
    content1 = await manager.get_source_content("test1.txt")
    assert content1 == "Hello from test1"
    
    content2 = await manager.get_source_content("test2.md")
    assert content2 == "Hello from test2"
    
    # 3. Test non-existent source
    with pytest.raises(FileNotFoundError):
        await manager.get_source_content("nonexistent.txt")

@pytest.mark.asyncio
async def test_get_source_content_pdf(temp_wiki):
    manager, _ = temp_wiki
    sources_dir = manager.sources_dir
    
    # Create a dummy PDF file (just a file with .pdf extension)
    pdf_path = os.path.join(sources_dir, "test.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 dummy content")
    
    # Mock PyPDFLoader
    from unittest.mock import MagicMock, patch
    
    mock_doc = MagicMock()
    mock_doc.page_content = "Extracted PDF text"
    
    with patch("langchain_community.document_loaders.PyPDFLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.return_value = [mock_doc]
        
        content = await manager.get_source_content("test.pdf")
        assert content == "Extracted PDF text"
        mock_loader_cls.assert_called_once_with(pdf_path)
