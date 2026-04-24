import os
from typing import Dict, Optional

import yaml

# Default _type.yaml definitions for the five built-in entity folders.
# Used to bootstrap volumes that pre-date the dynamic-folders feature.
_DEFAULT_TYPE_YAMLS: Dict[str, Dict] = {
    "clients": {
        "name": "Clients",
        "description": "Active client brands and fashion houses",
        "singular": "client",
        "fields": [
            {"name": "type", "type": "string", "default": "client"},
            {"name": "name", "type": "string", "required": True},
            {"name": "industry", "type": "string"},
            {"name": "tier", "type": "enum", "values": ["A", "B", "C"],
             "description": "A = active/high value, B = occasional, C = cold"},
            {"name": "status", "type": "enum", "values": ["active", "inactive"]},
            {"name": "hq", "type": "string"},
            {"name": "relationship_since", "type": "string"},
            {"name": "last_contact", "type": "date"},
            {"name": "source_count", "type": "integer"},
        ],
        "sections": ["Overview", "Key Contacts", "Production History",
                     "Relationship Notes", "Open Opportunities", "Sources"],
    },
    "contacts": {
        "name": "Contacts",
        "description": "Individual people across all organisations",
        "singular": "contact",
        "fields": [
            {"name": "type", "type": "string", "default": "contact"},
            {"name": "name", "type": "string", "required": True},
            {"name": "role", "type": "string"},
            {"name": "org", "type": "string"},
            {"name": "linked_orgs", "type": "list", "default": "[]"},
            {"name": "last_contact", "type": "date"},
        ],
        "sections": ["Bio", "Role & Responsibilities", "Relationship History",
                     "Productions Involved", "Notes"],
    },
    "photographers": {
        "name": "Photographers",
        "description": "Photographer roster and potential collaborators",
        "singular": "photographer",
        "fields": [
            {"name": "type", "type": "string", "default": "photographer"},
            {"name": "name", "type": "string", "required": True},
            {"name": "tier", "type": "enum", "values": ["A", "B", "C"],
             "description": "A = frequent collaborator, B = occasional, C = one-off/prospect"},
            {"name": "representation", "type": "string"},
            {"name": "based", "type": "string"},
            {"name": "speciality", "type": "list", "default": "[]"},
        ],
        "sections": ["Bio", "Style Notes", "Productions", "Client Relationships",
                     "Availability Notes", "Sources"],
    },
    "productions": {
        "name": "Productions",
        "description": "Individual shoot, project, or event pages",
        "singular": "production",
        "fields": [
            {"name": "entity_type", "type": "string", "default": "production"},
            {"name": "date", "type": "date"},
            {"name": "client", "type": "string"},
            {"name": "publication", "type": "string"},
            {"name": "photographer", "type": "string"},
            {"name": "location", "type": "string"},
            {"name": "work_type", "type": "enum",
             "values": ["editorial", "advertising", "lookbook", "show", "event"]},
            {"name": "status", "type": "enum",
             "values": ["complete", "in-progress", "pitched"]},
        ],
        "sections": ["Brief", "Team", "Outcome & Notes", "Sources"],
    },
    "prospects": {
        "name": "Prospects",
        "description": "Pipeline and potential clients or publications being actively pursued",
        "singular": "prospect",
        "fields": [
            {"name": "type", "type": "string", "default": "prospect"},
            {"name": "name", "type": "string", "required": True},
            {"name": "industry", "type": "string"},
            {"name": "tier", "type": "enum", "values": ["A", "B", "C"],
             "description": "A = high priority, B = medium, C = low/watch"},
            {"name": "status", "type": "enum", "values": ["prospect", "target"]},
            {"name": "hq", "type": "string"},
            {"name": "last_contact", "type": "date"},
            {"name": "source_count", "type": "integer"},
        ],
        "sections": ["Overview", "Key Contacts", "Why Farago",
                     "Outreach History", "Open Opportunities", "Sources"],
    },
}


def bootstrap_type_yamls(wiki_dir: str) -> None:
    """Seed _type.yaml into any built-in entity folder that is missing one.
    Safe to call on every startup — skips folders that already have the file.
    """
    for folder_name, type_data in _DEFAULT_TYPE_YAMLS.items():
        folder_path = os.path.join(wiki_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        yaml_path = os.path.join(folder_path, "_type.yaml")
        if os.path.exists(yaml_path):
            continue
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(type_data, f, default_flow_style=False, sort_keys=False)


def load_type_yaml(folder_path: str) -> Optional[Dict]:
    """Load _type.yaml from a folder. Returns None if not found."""
    yaml_path = os.path.join(folder_path, "_type.yaml")
    if not os.path.exists(yaml_path):
        return None
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def discover_entity_types(wiki_dir: str) -> Dict[str, Dict]:
    """Scan wiki_dir for subdirectories containing _type.yaml.
    Returns {folder_name: type_data} sorted alphabetically.
    """
    types = {}
    for entry in sorted(os.listdir(wiki_dir)):
        full = os.path.join(wiki_dir, entry)
        if not os.path.isdir(full):
            continue
        data = load_type_yaml(full)
        if data is not None:
            types[entry] = data
    return types


def render_type_schema_section(folder_name: str, type_data: Dict) -> str:
    """Render one entity type as a SCHEMA.md subsection."""
    singular = type_data.get("singular", folder_name.rstrip("s"))
    description = type_data.get("description", "")
    fields = type_data.get("fields", [])
    sections = type_data.get("sections", [])

    lines = [f"### {folder_name}/[{singular}-name].md"]
    if description:
        lines.append("")
        lines.append(f"*{description}*")
    lines.append("")
    lines.append("```yaml")
    lines.append("---")
    for field in fields:
        fname = field["name"]
        ftype = field.get("type", "string")
        if ftype == "enum":
            values = field.get("values", [])
            comment = field.get("description", "")
            value_str = " | ".join(str(v) for v in values)
            line = f"{fname}: {value_str}"
            if comment:
                line += f"          # {comment}"
            lines.append(line)
        elif ftype == "list":
            default = field.get("default", "[]")
            lines.append(f"{fname}: {default}")
        elif "default" in field:
            lines.append(f"{fname}: {field['default']}")
        else:
            lines.append(f"{fname}:")
    lines.append("---")
    lines.append("```")

    if sections:
        lines.append("")
        section_str = " · ".join(f"`## {s}`" for s in sections)
        lines.append(f"Sections: {section_str}")

    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def _render_directory_tree(types: Dict[str, Dict]) -> str:
    """Render the entity types as directory tree entries for SCHEMA.md."""
    lines = []
    for folder_name, type_data in types.items():
        singular = type_data.get("singular", folder_name.rstrip("s"))
        description = type_data.get("description", "")
        comment = f"  # {description}" if description else ""
        lines.append(f"├── {folder_name}/{comment}")
        lines.append(f"│   └── [{singular}-name].md")
    return "\n".join(lines)


def build_schema_md(wiki_dir: str, template_path: str) -> str:
    """Assemble SCHEMA.md from the template and _type.yaml files."""
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    types = discover_entity_types(wiki_dir)

    # Build directory tree block
    directory_block = _render_directory_tree(types)

    # Build schema sections block
    schema_sections = []
    for folder_name, type_data in types.items():
        schema_sections.append(render_type_schema_section(folder_name, type_data))
    schemas_block = "\n".join(schema_sections)

    result = template.replace("{{ENTITY_TYPES_DIRECTORY}}", directory_block)
    result = result.replace("{{ENTITY_TYPES_SCHEMAS}}", schemas_block)
    return result


def generate_entity_template(
    folder_name: str,
    singular: str,
    fields: list,
    sections: list,
) -> str:
    """Generate a new entity instance template with frontmatter and sections."""
    fm_lines = [f"type: {singular}"]
    for field in fields:
        fname = field.get("name", "")
        if fname == "type":
            continue  # already emitted as first line
        ftype = field.get("type", "string")
        if ftype == "list":
            fm_lines.append(f"{fname}: []")
        elif ftype == "enum":
            values = field.get("values", [])
            fm_lines.append(f"{fname}:  # options: {', '.join(str(v) for v in values)}")
        elif "default" in field:
            fm_lines.append(f"{fname}: {field['default']}")
        else:
            fm_lines.append(f"{fname}: ")

    lines = ["---"] + fm_lines + ["---", "", "# ", ""]
    for section in sections:
        lines.append(f"## {section}")
        lines.append(f"_Add {section.lower()} here..._")
        lines.append("")
    return "\n".join(lines)
