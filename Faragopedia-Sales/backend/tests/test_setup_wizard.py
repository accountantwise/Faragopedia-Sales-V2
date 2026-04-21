import os
import tempfile
from unittest.mock import patch
from agent.wiki_manager import WikiManager

def test_wiki_manager_init_without_schema_files():
    """WikiManager should not crash when SCHEMA.md and company_profile.md are absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_dir = os.path.join(tmpdir, "wiki")
        os.makedirs(wiki_dir)
        schema_dir = os.path.join(tmpdir, "schema")
        os.makedirs(schema_dir)
        # No SCHEMA.md, no company_profile.md, no SCHEMA_TEMPLATE.md
        # Should not raise
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test_key",
            "AI_PROVIDER": "openai",
            "AI_MODEL": "gpt-4o-mini",
        }):
            wm = WikiManager(
                sources_dir=os.path.join(tmpdir, "sources"),
                wiki_dir=wiki_dir,
                archive_dir=os.path.join(tmpdir, "archive"),
                snapshots_dir=os.path.join(tmpdir, "snapshots"),
                schema_dir=schema_dir,
            )
        assert wm is not None
