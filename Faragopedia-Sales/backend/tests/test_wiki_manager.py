import asyncio
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from agent.wiki_manager import (
    WikiManager, WikiPage, FaragoIngestionResult, LintFinding, LintReport,
    LintFixPlan, FixReport, Snapshot
)

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

def test_wiki_manager_has_write_lock(temp_dirs):
    """_write_lock must exist and be an asyncio.Lock."""
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)
    assert hasattr(manager, '_write_lock')
    assert isinstance(manager._write_lock, asyncio.Lock)


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


@pytest.fixture
def schema_dirs(tmp_path):
    """Create fake schema files for tests."""
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Test Schema\nYou are the Farago wiki agent.")
    (schema_dir / "company_profile.md").write_text("# Farago Projects\nA creative production house.")
    return str(schema_dir)


@pytest.fixture
def temp_dirs_with_schema(tmp_path, schema_dirs):
    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    return str(sources), str(wiki), schema_dirs


def test_wiki_page_model():
    page = WikiPage(
        path="clients/louis-vuitton.md",
        content="---\ntype: client\nname: Louis Vuitton\n---\n# Louis Vuitton\n",
        action="create"
    )
    assert page.path == "clients/louis-vuitton.md"
    assert page.action == "create"
    assert "Louis Vuitton" in page.content


def test_wiki_page_action_values():
    create_page = WikiPage(path="clients/foo.md", content="# Foo", action="create")
    update_page = WikiPage(path="clients/foo.md", content="# Foo updated", action="update")
    assert create_page.action == "create"
    assert update_page.action == "update"


def test_farago_ingestion_result_model():
    result = FaragoIngestionResult(
        pages=[
            WikiPage(path="clients/louis-vuitton.md", content="# LV", action="create"),
            WikiPage(path="contacts/jane-doe.md", content="# Jane", action="create"),
        ],
        log_entry="Ingested LV press release. Created 2 pages: clients/louis-vuitton, contacts/jane-doe."
    )
    assert len(result.pages) == 2
    assert result.pages[0].path == "clients/louis-vuitton.md"
    assert "jane-doe" in result.log_entry


def test_lint_finding_model():
    finding = LintFinding(
        severity="warning",
        page="clients/louis-vuitton.md",
        description="Missing 'last_contact' field in frontmatter."
    )
    assert finding.severity == "warning"
    assert finding.page == "clients/louis-vuitton.md"


def test_lint_report_model():
    report = LintReport(
        findings=[
            LintFinding(severity="error", page="global", description="Orphan page: photographers/unknown.md"),
            LintFinding(severity="warning", page="clients/chanel.md", description="tier field is empty"),
            LintFinding(severity="suggestion", page="global", description="Consider adding Dior as a prospect"),
        ],
        summary="1 error, 1 warning, 1 suggestion found."
    )
    assert len(report.findings) == 3
    errors = [f for f in report.findings if f.severity == "error"]
    assert len(errors) == 1


def test_lint_finding_has_fix_fields():
    finding = LintFinding(
        severity="warning",
        page="clients/louis-vuitton.md",
        description="Missing 'last_contact' field.",
        fix_confidence="full",
        fix_description="Add a last_contact field to the frontmatter.",
    )
    assert finding.fix_confidence == "full"
    assert finding.fix_description == "Add a last_contact field to the frontmatter."


def test_lint_finding_fix_fields_default():
    finding = LintFinding(
        severity="warning",
        page="clients/acme.md",
        description="Some issue.",
    )
    assert finding.fix_confidence == "stub"
    assert finding.fix_description == ""


def test_lint_fix_plan_model():
    from agent.wiki_manager import LintFixPlan
    plan = LintFixPlan(
        pages=[WikiPage(path="concepts/e-sign.md", content="# E-Sign\n\nStub.", action="create")],
        skipped=["needs_source: Whitmore bottleneck pages"],
        summary="Fixed 1 finding: created 1 stub.",
    )
    assert len(plan.pages) == 1
    assert plan.pages[0].path == "concepts/e-sign.md"
    assert len(plan.skipped) == 1


def test_fix_report_model():
    from agent.wiki_manager import FixReport
    report = FixReport(
        files_changed=["concepts/e-sign.md"],
        skipped=["needs_source: Whitmore bottleneck pages"],
        summary="Fixed 1 finding: created 1 stub.",
        snapshot_id="20260420-143201",
    )
    assert report.snapshot_id == "20260420-143201"
    assert "concepts/e-sign.md" in report.files_changed


def test_snapshot_model():
    from agent.wiki_manager import Snapshot
    snap = Snapshot(
        id="20260420-143201",
        label="pre-lint 2026-04-20 14:32",
        created_at="2026-04-20T14:32:01",
        file_count=12,
    )
    assert snap.id == "20260420-143201"
    assert snap.file_count == 12


def test_system_prompt_loaded_from_schema_dir(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# SCHEMA CONTENT")
    (schema_dir / "company_profile.md").write_text("# PROFILE CONTENT")

    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(sources),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    assert "SCHEMA CONTENT" in manager.system_prompt
    assert "PROFILE CONTENT" in manager.system_prompt


def test_system_prompt_raises_if_schema_missing(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    # Only create SCHEMA.md, not company_profile.md
    (schema_dir / "SCHEMA.md").write_text("# Schema")

    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        with pytest.raises(FileNotFoundError):
            WikiManager(
                sources_dir=str(sources),
                wiki_dir=str(wiki),
                schema_dir=str(schema_dir)
            )


def test_list_pages_returns_subdirectory_paths(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "photographers").mkdir()
    (wiki / "clients" / "louis-vuitton.md").write_text("---\ntype: client\n---\n# LV")
    (wiki / "photographers" / "jamie-hawkesworth.md").write_text("---\ntype: photographer\n---\n# JH")
    (wiki / "index.md").write_text("# Index")
    (wiki / "log.md").write_text("# Log")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    pages = manager.list_pages()
    assert "clients/louis-vuitton.md" in pages
    assert "photographers/jamie-hawkesworth.md" in pages
    assert "index.md" not in pages
    assert "log.md" not in pages


def test_update_index_groups_by_subdirectory(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    entity_meta = {
        "clients": "Clients", "prospects": "Prospects", "contacts": "Contacts",
        "photographers": "Photographers", "productions": "Productions",
    }
    for sub, name in entity_meta.items():
        (wiki / sub).mkdir()
        (wiki / sub / "_type.yaml").write_text(
            f"name: {name}\nsingular: {sub.rstrip('s')}\nfields: []\nsections: []\n"
        )
    (wiki / "clients" / "louis-vuitton.md").write_text("# LV")
    (wiki / "prospects" / "chanel.md").write_text("# Chanel")
    (wiki / "photographers" / "jamie-hawkesworth.md").write_text("# JH")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    manager.update_index()
    index_content = (wiki / "index.md").read_text()

    assert "## Clients" in index_content
    assert "[[clients/louis-vuitton]]" in index_content
    assert "## Prospects" in index_content
    assert "[[prospects/chanel]]" in index_content
    assert "## Photographers" in index_content
    assert "[[photographers/jamie-hawkesworth]]" in index_content


def test_get_backlinks_across_subdirectories(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "contacts").mkdir()
    (wiki / "productions").mkdir()

    (wiki / "clients" / "louis-vuitton.md").write_text(
        "# LV\n\nKey contact: [[contacts/jane-doe]]"
    )
    (wiki / "productions" / "2026-02-lv-editorial.md").write_text(
        "# LV Editorial\n\nClient: [[clients/louis-vuitton]]"
    )
    (wiki / "contacts" / "jane-doe.md").write_text("# Jane Doe\n\nWorks at [[clients/louis-vuitton]]")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    backlinks = manager.get_backlinks("clients/louis-vuitton.md")
    assert "productions/2026-02-lv-editorial.md" in backlinks
    assert "contacts/jane-doe.md" in backlinks


import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("OPENAI_API_KEY", "test_key_for_import")
from api.routes import safe_wiki_filename


def test_safe_wiki_filename_allows_known_subdirs():
    known = {"clients", "prospects", "contacts", "photographers", "productions"}
    entity_types = {sub: {"name": sub.capitalize()} for sub in known}
    with patch('api.routes.wiki_manager') as mock_wm:
        mock_wm.get_entity_types.return_value = entity_types
        for sub in known:
            result = safe_wiki_filename(f"{sub}/some-page.md")
            assert result == f"{sub}/some-page.md"


def test_safe_wiki_filename_rejects_unknown_subdir():
    with pytest.raises(ValueError, match="Invalid entity subdirectory"):
        safe_wiki_filename("evil/foo.md")


def test_safe_wiki_filename_rejects_flat_path():
    with pytest.raises(ValueError, match="Invalid entity subdirectory"):
        safe_wiki_filename("louis-vuitton.md")


def test_safe_wiki_filename_rejects_traversal():
    with pytest.raises(ValueError):
        safe_wiki_filename("../etc/passwd.md")
    with pytest.raises(ValueError):
        safe_wiki_filename("clients/../secrets.md")


def test_safe_wiki_filename_rejects_non_md():
    with pytest.raises(ValueError, match=".md"):
        safe_wiki_filename("clients/foo.txt")


@pytest.mark.asyncio
async def test_ingest_writes_pages_to_correct_subdirectory(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    entity_meta = {
        "clients": "Clients", "contacts": "Contacts", "prospects": "Prospects",
        "photographers": "Photographers", "productions": "Productions",
    }
    for sub, name in entity_meta.items():
        (wiki / sub).mkdir()
        (wiki / sub / "_type.yaml").write_text(
            f"name: {name}\nsingular: {sub.rstrip('s')}\nfields: []\nsections: []\n"
        )
    (wiki / "index.md").write_text("# Index\n\n## Clients\n\n*No clients yet.*\n")

    source_file = sources / "lv-brief.txt"
    source_file.write_text("Louis Vuitton is an A-tier client. Contact: Sophie Martin.")

    mock_result = FaragoIngestionResult(
        pages=[
            WikiPage(
                path="clients/louis-vuitton.md",
                content="---\ntype: client\nname: Louis Vuitton\ntier: A\nstatus: active\n---\n# Louis Vuitton\n\n## Overview\n\nLuxury fashion house.\n",
                action="create"
            ),
            WikiPage(
                path="contacts/sophie-martin.md",
                content="---\ntype: contact\nname: Sophie Martin\norg: Louis Vuitton\n---\n# Sophie Martin\n\n## Role & Responsibilities\n\nKey contact at [[clients/louis-vuitton]].\n",
                action="create"
            ),
        ],
        log_entry="Ingested lv-brief.txt. Created 2 pages: clients/louis-vuitton, contacts/sophie-martin."
    )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(sources),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    with patch.object(manager, '_run_ingest_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_result
        await manager.ingest_source("lv-brief.txt")

    assert (wiki / "clients" / "louis-vuitton.md").exists()
    lv_content = (wiki / "clients" / "louis-vuitton.md").read_text()
    assert "tier: A" in lv_content

    assert (wiki / "contacts" / "sophie-martin.md").exists()
    sophie_content = (wiki / "contacts" / "sophie-martin.md").read_text()
    assert "[[clients/louis-vuitton]]" in sophie_content

    index_content = (wiki / "index.md").read_text()
    assert "[[clients/louis-vuitton]]" in index_content

    log_content = (wiki / "log.md").read_text()
    assert "lv-brief.txt" in log_content

    metadata = manager.get_sources_metadata()
    assert metadata["lv-brief.txt"]["ingested"] is True


@pytest.mark.asyncio
async def test_ingest_source_not_found(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(tmp_path / "wiki"),
            schema_dir=str(schema_dir)
        )

    with pytest.raises(FileNotFoundError):
        await manager.ingest_source("nonexistent.txt")


@pytest.mark.asyncio
async def test_ingest_retries_on_llm_failure(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    sources = tmp_path / "sources"
    wiki = tmp_path / "wiki"
    sources.mkdir()
    wiki.mkdir()
    (wiki / "index.md").write_text("# Index")
    (sources / "test.txt").write_text("Test content")

    success_result = FaragoIngestionResult(
        pages=[WikiPage(path="clients/test.md", content="# Test", action="create")],
        log_entry="Ingested test.txt"
    )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(sources),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    # Fail once, succeed on second attempt
    (wiki / "clients").mkdir()
    call_count = [0]
    async def flaky_llm(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("LLM output validation failed")
        return success_result

    with patch.object(manager, '_run_ingest_llm', side_effect=flaky_llm):
        await manager.ingest_source("test.txt")

    assert call_count[0] == 2
    assert (wiki / "clients" / "test.md").exists()


@pytest.mark.asyncio
async def test_query_uses_system_prompt(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema — you are the Farago wiki agent")
    (schema_dir / "company_profile.md").write_text("# Farago Projects profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "louis-vuitton.md").write_text(
        "---\ntype: client\nname: Louis Vuitton\ntier: A\n---\n# Louis Vuitton\n\n## Overview\n\nA luxury fashion house."
    )
    (wiki / "index.md").write_text(
        "# Index\n\n## Clients\n\n- [[clients/louis-vuitton]] | last updated: 2026-04-16\n"
    )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    captured_calls = []

    async def mock_run_query(user_query, index_content, context):
        captured_calls.append({
            "query": user_query,
            "index": index_content,
            "context": context,
        })
        return "Louis Vuitton is an A-tier client. [[clients/louis-vuitton]]"

    with patch.object(manager, '_run_query_llm', side_effect=mock_run_query):
        response = await manager.query("Who are our top clients?")

    assert response == "Louis Vuitton is an A-tier client. [[clients/louis-vuitton]]"
    assert len(captured_calls) == 1
    assert "louis-vuitton" in captured_calls[0]["context"].lower()

    log_content = (wiki / "log.md").read_text()
    assert "query" in log_content


@pytest.mark.asyncio
async def test_lint_returns_report(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "clients").mkdir()
    (wiki / "clients" / "louis-vuitton.md").write_text(
        "---\ntype: client\nname: Louis Vuitton\ntier: A\n---\n# Louis Vuitton\n"
    )
    (wiki / "index.md").write_text("# Index\n\n## Clients\n\n- [[clients/louis-vuitton]]\n")

    mock_report = LintReport(
        findings=[
            LintFinding(
                severity="warning",
                page="clients/louis-vuitton.md",
                description="Missing 'last_contact' field in frontmatter."
            )
        ],
        summary="1 warning found."
    )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    with patch.object(manager, '_run_lint_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_report
        report = await manager.lint()

    assert isinstance(report, LintReport)
    assert len(report.findings) == 1
    assert report.findings[0].severity == "warning"
    assert report.summary == "1 warning found."

    # Lint is read-only — no files written except log
    log_content = (wiki / "log.md").read_text()
    assert "lint" in log_content


def test_health_check_no_longer_exists(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(tmp_path / "wiki"),
            schema_dir=str(schema_dir)
        )

    assert not hasattr(manager, 'health_check'), \
        "health_check() should be removed — use lint() instead"


@pytest.mark.asyncio
async def test_create_new_page_in_entity_subdir(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    entity_meta = {
        "clients": "Clients", "prospects": "Prospects", "contacts": "Contacts",
        "photographers": "Photographers", "productions": "Productions",
    }
    for sub, name in entity_meta.items():
        (wiki / sub).mkdir()
        (wiki / sub / "_type.yaml").write_text(
            f"name: {name}\nsingular: {sub.rstrip('s')}\nfields: []\nsections: []\n"
        )

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(wiki),
            schema_dir=str(schema_dir)
        )

    filename = await manager.create_new_page(entity_type="clients")
    assert filename == "clients/Untitled.md"
    assert (wiki / "clients" / "Untitled.md").exists()

    # Second creation → collision handling
    filename2 = await manager.create_new_page(entity_type="clients")
    assert filename2 == "clients/Untitled_1.md"

    # Photographers subdir
    filename3 = await manager.create_new_page(entity_type="photographers")
    assert filename3 == "photographers/Untitled.md"


@pytest.mark.asyncio
async def test_create_new_page_rejects_invalid_type(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    (schema_dir / "SCHEMA.md").write_text("# Schema")
    (schema_dir / "company_profile.md").write_text("# Profile")

    with patch('agent.wiki_manager.WikiManager._init_llm', return_value=MagicMock()):
        manager = WikiManager(
            sources_dir=str(tmp_path / "sources"),
            wiki_dir=str(tmp_path / "wiki"),
            schema_dir=str(schema_dir)
        )

    with pytest.raises(ValueError, match="Invalid entity type"):
        await manager.create_new_page(entity_type="invoices")
