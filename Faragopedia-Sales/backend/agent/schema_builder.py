import os
from typing import Dict, Optional

import yaml


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
