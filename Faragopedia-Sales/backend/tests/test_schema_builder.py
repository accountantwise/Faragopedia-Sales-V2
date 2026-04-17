import os
import pytest
import yaml
from agent.schema_builder import (
    load_type_yaml,
    discover_entity_types,
    render_type_schema_section,
    build_schema_md,
)


@pytest.fixture
def wiki_with_types(tmp_path):
    """Create a wiki dir with two entity folders and _type.yaml files."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    clients = wiki / "clients"
    clients.mkdir()
    (clients / "_type.yaml").write_text(yaml.dump({
        "name": "Clients",
        "description": "Active client brands",
        "singular": "client",
        "fields": [
            {"name": "type", "type": "string", "default": "client"},
            {"name": "name", "type": "string", "required": True},
            {"name": "tier", "type": "enum", "values": ["A", "B", "C"]},
        ],
        "sections": ["Overview", "Key Contacts", "Sources"],
    }))

    stylists = wiki / "stylists"
    stylists.mkdir()
    (stylists / "_type.yaml").write_text(yaml.dump({
        "name": "Stylists",
        "description": "Hair and makeup stylists",
        "singular": "stylist",
        "fields": [
            {"name": "type", "type": "string", "default": "stylist"},
            {"name": "name", "type": "string", "required": True},
            {"name": "agency", "type": "string"},
        ],
        "sections": ["Bio", "Productions"],
    }))

    # A folder without _type.yaml should be ignored
    (wiki / "sources").mkdir()

    return str(wiki)


def test_load_type_yaml(wiki_with_types):
    data = load_type_yaml(os.path.join(wiki_with_types, "clients"))
    assert data["name"] == "Clients"
    assert data["singular"] == "client"
    assert len(data["fields"]) == 3


def test_load_type_yaml_missing_file(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = load_type_yaml(str(empty))
    assert result is None


def test_discover_entity_types(wiki_with_types):
    types = discover_entity_types(wiki_with_types)
    names = sorted(types.keys())
    assert names == ["clients", "stylists"]
    assert types["clients"]["name"] == "Clients"
    assert types["stylists"]["name"] == "Stylists"


def test_discover_skips_dirs_without_type_yaml(wiki_with_types):
    types = discover_entity_types(wiki_with_types)
    assert "sources" not in types


def test_render_type_schema_section():
    type_data = {
        "name": "Clients",
        "singular": "client",
        "description": "Active client brands",
        "fields": [
            {"name": "type", "type": "string", "default": "client"},
            {"name": "name", "type": "string", "required": True},
            {"name": "tier", "type": "enum", "values": ["A", "B", "C"]},
        ],
        "sections": ["Overview", "Key Contacts"],
    }
    section = render_type_schema_section("clients", type_data)
    assert "### clients/[" in section
    assert "type: client" in section or "type:" in section
    assert "tier: A | B | C" in section
    assert "## Overview" in section or "`## Overview`" in section


def test_build_schema_md(wiki_with_types, tmp_path):
    template_path = tmp_path / "SCHEMA_TEMPLATE.md"
    template_path.write_text(
        "# SCHEMA.md\n\nFixed content here.\n\n"
        "{{ENTITY_TYPES_DIRECTORY}}\n\n"
        "{{ENTITY_TYPES_SCHEMAS}}\n\n"
        "## Operations\n\nFixed operations.\n"
    )
    result = build_schema_md(wiki_with_types, str(template_path))
    assert "# SCHEMA.md" in result
    assert "clients/" in result
    assert "stylists/" in result
    assert "## Operations" in result
    assert "{{ENTITY_TYPES_DIRECTORY}}" not in result
    assert "{{ENTITY_TYPES_SCHEMAS}}" not in result
