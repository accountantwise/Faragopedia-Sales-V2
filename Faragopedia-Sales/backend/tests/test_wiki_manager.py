import asyncio
import pytest
import os
from unittest.mock import patch, AsyncMock
from agent.wiki_manager import WikiManager, IngestionResult, Entity

@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "AI_PROVIDER": "openai",
        "AI_MODEL": "gpt-4o-mini"
    }):
        yield

@pytest.fixture
def temp_dirs(tmp_path):
    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    return str(sources), str(wiki)

def test_wiki_manager_init(temp_dirs):
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)
    assert manager.sources_dir == sources
    assert manager.wiki_dir == wiki
    assert os.path.exists(sources)
    assert os.path.exists(wiki)

@pytest.mark.asyncio
async def test_wiki_manager_ingest_source_cycle(temp_dirs):
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)
    
    # Create dummy source
    test_filename = "test_source.txt"
    source_path = os.path.join(sources, test_filename)
    with open(source_path, "w", encoding="utf-8") as f:
        f.write("Artificial Intelligence is a branch of computer science.")

    # Mock ingestion result
    mock_result = IngestionResult(
        source_summary="A document about AI.",
        entities=[
            Entity(name="AI", summary="Artificial Intelligence", details="Detailed AI info")
        ]
    )

    # Mock the internal chain creation and execution
    with patch("agent.wiki_manager.PromptTemplate", autospec=True) as mock_prompt, \
         patch("agent.wiki_manager.PydanticOutputParser", autospec=True) as mock_parser:
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_result
        
        # Setup the chain piping mock: prompt | llm | parser
        mock_prompt_inst = mock_prompt.return_value
        mock_prompt_inst.__or__.return_value.__or__.return_value = mock_chain
        
        result = await manager.ingest_source(test_filename)
        
        assert result == mock_result
        
    # Verify files created
    summary_path = os.path.join(wiki, f"Summary_{test_filename}.md")
    entity_path = os.path.join(wiki, "AI.md")
    index_path = os.path.join(wiki, "index.md")
    log_path = os.path.join(wiki, "log.md")
    
    assert os.path.exists(summary_path)
    assert os.path.exists(entity_path)
    assert os.path.exists(index_path)
    assert os.path.exists(log_path)
    
    with open(summary_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "A document about AI." in content
        assert "[[AI]]" in content
        
    with open(entity_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# AI" in content
        assert "Artificial Intelligence" in content
        assert "Detailed AI info" in content
        
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "[[Summary_test_source.txt]]" in content
        assert "[[AI]]" in content

def test_wiki_manager_log(temp_dirs):
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)
    manager._append_to_log("test_action", "test_details")
    
    log_path = os.path.join(wiki, "log.md")
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        content = f.read()
        assert "test_action" in content
        assert "test_details" in content

@pytest.mark.asyncio
async def test_wiki_manager_query(temp_dirs):
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)
    
    # Create a dummy page
    page_name = "AI"
    with open(os.path.join(wiki, f"{page_name}.md"), "w", encoding="utf-8") as f:
        f.write("# AI\nArtificial Intelligence is a branch of computer science.")
        
    # Create index.md
    with open(os.path.join(wiki, "index.md"), "w", encoding="utf-8") as f:
        f.write(f"- [[{page_name}]]")

    # Mock LLM response for relevance and answer
    # We need to mock the invoke/ainvoke of the chains
    with patch("agent.wiki_manager.PromptTemplate", autospec=True) as mock_prompt:
        mock_relevance_chain = AsyncMock()
        mock_relevance_chain.ainvoke.return_value = AsyncMock(content="AI")
        
        mock_answer_chain = AsyncMock()
        mock_answer_chain.ainvoke.return_value = AsyncMock(content="Artificial Intelligence is computer science.")
        
        # This is a bit complex due to how chains are piped in LangChain
        # For simplicity, we can mock the pipe operation or the final chain
        
        # Setup mock_prompt instances to return our mock chains when piped
        mock_prompt_inst = mock_prompt.return_value
        # First pipe is for relevance_chain
        mock_prompt_inst.__or__.side_effect = [mock_relevance_chain, mock_answer_chain]
        
        response = await manager.query("What is AI?")
        
        assert "Artificial Intelligence" in response
        assert response == "Artificial Intelligence is computer science."


def test_wiki_manager_has_write_lock(temp_dirs):
    """_write_lock must exist and be an asyncio.Lock."""
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)
    assert hasattr(manager, '_write_lock')
    assert isinstance(manager._write_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_concurrent_ingestion_no_corruption(temp_dirs):
    """Two simultaneous ingestions must both appear in index.md and log.md."""
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)

    # Create two source files
    for name in ["alpha.txt", "beta.txt"]:
        with open(os.path.join(sources, name), "w", encoding="utf-8") as f:
            f.write(f"Content of {name}")

    mock_result_alpha = IngestionResult(
        source_summary="Summary of alpha.",
        entities=[Entity(name="AlphaEntity", summary="Alpha summary", details="Alpha details")]
    )
    mock_result_beta = IngestionResult(
        source_summary="Summary of beta.",
        entities=[Entity(name="BetaEntity", summary="Beta summary", details="Beta details")]
    )

    call_results = [mock_result_alpha, mock_result_beta]
    call_count = [0]

    async def mock_ainvoke(_data):
        # Yield to event loop once so coroutines can interleave at the LLM phase.
        # Note: a single sleep(0) does not guarantee lock contention — this test
        # verifies output correctness (both results written), not that the lock
        # is load-bearing under simultaneous writes.
        await asyncio.sleep(0)
        result = call_results[call_count[0] % 2]
        call_count[0] += 1
        return result

    with patch("agent.wiki_manager.PromptTemplate", autospec=True) as mock_prompt, \
         patch("agent.wiki_manager.PydanticOutputParser", autospec=True):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = mock_ainvoke
        mock_prompt.return_value.__or__.return_value.__or__.return_value = mock_chain

        await asyncio.gather(
            manager.ingest_source("alpha.txt"),
            manager.ingest_source("beta.txt"),
        )

    index_path = os.path.join(wiki, "index.md")
    with open(index_path, "r", encoding="utf-8") as f:
        index_content = f.read()

    assert "[[AlphaEntity]]" in index_content, "AlphaEntity missing from index.md"
    assert "[[BetaEntity]]" in index_content, "BetaEntity missing from index.md"

    log_path = os.path.join(wiki, "log.md")
    with open(log_path, "r", encoding="utf-8") as f:
        log_content = f.read()

    assert log_content.count("Processed") == 2, "Expected 2 log entries, got fewer"

@pytest.mark.asyncio
async def test_create_new_page(temp_dirs):
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki, archive_dir=os.path.join(os.path.dirname(wiki), "archive"))
    filename = await manager.create_new_page()
    assert filename == "Untitled.md"
    assert os.path.exists(os.path.join(manager.wiki_dir, filename))
    
    # Test collision
    filename2 = await manager.create_new_page()
    assert filename2 == "Untitled_1.md"
    assert os.path.exists(os.path.join(manager.wiki_dir, filename2))

@pytest.mark.asyncio
async def test_archive_and_restore_page(temp_dirs):
    sources, wiki = temp_dirs
    archive = os.path.join(os.path.dirname(wiki), "archive")
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki, archive_dir=archive)
    
    # Setup: Create a page
    filename = "test_page.md"
    path = os.path.join(manager.wiki_dir, filename)
    with open(path, "w") as f:
        f.write("# Test")
    
    # 1. Archive
    await manager.archive_page(filename)
    assert not os.path.exists(path)
    assert os.path.exists(os.path.join(manager.archive_wiki_dir, filename))
    
    # 2. Restore
    await manager.restore_page(filename)
    assert os.path.exists(path)
    assert not os.path.exists(os.path.join(manager.archive_wiki_dir, filename))

@pytest.mark.asyncio
async def test_archive_and_restore_source(temp_dirs):
    sources, wiki = temp_dirs
    archive = os.path.join(os.path.dirname(wiki), "archive")
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki, archive_dir=archive)
    
    # Setup: Create a source
    filename = "test_source.txt"
    path = os.path.join(manager.sources_dir, filename)
    with open(path, "w") as f:
        f.write("test content")
    
    # 1. Archive
    await manager.archive_source(filename)
    assert not os.path.exists(path)
    assert os.path.exists(os.path.join(manager.archive_sources_dir, filename))
    
    # 2. Restore
    await manager.restore_source(filename)
    assert os.path.exists(path)
    assert not os.path.exists(os.path.join(manager.archive_sources_dir, filename))

@pytest.mark.asyncio
async def test_permanent_delete(temp_dirs):
    sources, wiki = temp_dirs
    archive = os.path.join(os.path.dirname(wiki), "archive")
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki, archive_dir=archive)
    
    # Setup: Create and archive a page
    filename = "delete_me.md"
    path = os.path.join(manager.wiki_dir, filename)
    with open(path, "w") as f:
        f.write("# Delete Me")
    
    await manager.archive_page(filename)
    archive_path = os.path.join(manager.archive_wiki_dir, filename)
    assert os.path.exists(archive_path)
    
    # Permanent delete
    await manager.delete_archived_page(filename)
    assert not os.path.exists(archive_path)

@pytest.mark.asyncio
async def test_list_archived(temp_dirs):
    sources, wiki = temp_dirs
    archive = os.path.join(os.path.dirname(wiki), "archive")
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki, archive_dir=archive)
    
    # Setup: Archive something
    p_filename = "archived_page.md"
    s_filename = "archived_source.txt"
    
    with open(os.path.join(manager.wiki_dir, p_filename), "w") as f:
        f.write("# Page")
    with open(os.path.join(manager.sources_dir, s_filename), "w") as f:
        f.write("Source")
        
    await manager.archive_page(p_filename)
    await manager.archive_source(s_filename)
    
    pages = manager.list_archived_pages()
    sources = manager.list_archived_sources()
    
    assert p_filename in pages
    assert s_filename in sources

@pytest.mark.asyncio
async def test_metadata_tracking(temp_dirs):
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)
    
    filename = "test.txt"
    with open(os.path.join(sources, filename), "w") as f:
        f.write("content")
        
    # Initially not ingested
    meta = manager.get_sources_metadata()
    assert filename in meta
    assert meta[filename]["ingested"] is False
    
    # Mark as ingested
    manager.mark_source_ingested(filename, True)
    meta = manager.get_sources_metadata()
    assert meta[filename]["ingested"] is True
    assert meta[filename]["ingested_at"] is not None
    
    # Persistent across manager re-init
    manager2 = WikiManager(sources_dir=sources, wiki_dir=wiki)
    meta2 = manager2.get_sources_metadata()
    assert meta2[filename]["ingested"] is True
