import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from api.routes import (
    ARCHIVE_DIR,
    SNAPSHOTS_DIR,
    SOURCES_DIR,
    WIKI_DIR,
    set_wiki_manager,
)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
SCHEMA_DIR = os.path.join(_BACKEND_DIR, "schema")

export_router = APIRouter()

_APP_VERSION = "1.0.0"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


@export_router.get("/bundle/full")
def export_bundle_full():
    manifest = {
        "version": 1,
        "type": "full",
        "exported_at": _utcnow(),
        "app_version": _APP_VERSION,
    }
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            for dir_name, dir_str in [
                ("schema", SCHEMA_DIR),
                ("wiki", WIKI_DIR),
                ("sources", SOURCES_DIR),
                ("archive", ARCHIVE_DIR),
                ("snapshots", SNAPSHOTS_DIR),
            ]:
                dir_path = Path(dir_str)
                if not dir_path.exists():
                    continue
                for fp in sorted(dir_path.rglob("*")):
                    if fp.is_file():
                        rel = str(fp.relative_to(dir_path)).replace("\\", "/")
                        zf.write(fp, f"{dir_name}/{rel}")
        buf.seek(0)
        ts = _timestamp()
        return Response(
            content=buf.read(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="faragopedia-full-{ts}.zip"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Export failed") from exc


@export_router.get("/bundle/template")
def export_bundle_template():
    manifest = {
        "version": 1,
        "type": "template",
        "exported_at": _utcnow(),
        "app_version": _APP_VERSION,
    }
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            schema_path = Path(SCHEMA_DIR)
            if schema_path.exists():
                for fp in sorted(schema_path.rglob("*")):
                    if fp.is_file():
                        rel = str(fp.relative_to(schema_path)).replace("\\", "/")
                        zf.write(fp, f"schema/{rel}")
            wiki_path = Path(WIKI_DIR)
            if wiki_path.exists():
                for fp in sorted(wiki_path.rglob("_type.yaml")):
                    rel = str(fp.relative_to(wiki_path)).replace("\\", "/")
                    zf.write(fp, f"wiki/{rel}")
        buf.seek(0)
        ts = _timestamp()
        return Response(
            content=buf.read(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="faragopedia-template-{ts}.zip"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Export failed") from exc


@export_router.post("/import")
async def import_bundle(file: UploadFile = File(...)):
    content = await file.read()

    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive")

    with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
        names = set(zf.namelist())

        if "manifest.json" not in names:
            raise HTTPException(status_code=400, detail="Missing manifest.json — not a Faragopedia bundle")

        manifest = json.loads(zf.read("manifest.json"))

        if manifest.get("version") != 1:
            raise HTTPException(
                status_code=400,
                detail=f"Incompatible bundle version {manifest.get('version')!r}. Expected 1.",
            )

        bundle_type = manifest.get("type")
        if bundle_type not in ("full", "template"):
            raise HTTPException(status_code=400, detail=f"Unknown bundle type {bundle_type!r}")

        if "schema/wiki_config.json" not in names:
            raise HTTPException(status_code=400, detail="Missing schema/wiki_config.json in bundle")

        wiki_config = json.loads(zf.read("schema/wiki_config.json"))

        with tempfile.TemporaryDirectory() as staging_str:
            staging = Path(staging_str)
            zf.extractall(staging)

            try:
                if bundle_type == "full":
                    _restore_full(staging)
                    _reinit_wiki_manager()
                    return {"status": "ok", "type": "full"}
                else:
                    entity_types = _restore_template(staging, wiki_config)
                    return {
                        "status": "ok",
                        "type": "template",
                        "wiki_name": wiki_config.get("wiki_name", ""),
                        "org_name": wiki_config.get("org_name", ""),
                        "org_description": wiki_config.get("org_description", ""),
                        "entity_types": entity_types,
                        "folders": [et["folder_name"] for et in entity_types],
                    }
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Restore failed: {exc}") from exc


def _restore_full(staging: Path) -> None:
    for dir_name, dir_str in [
        ("schema", SCHEMA_DIR),
        ("wiki", WIKI_DIR),
        ("sources", SOURCES_DIR),
        ("archive", ARCHIVE_DIR),
        ("snapshots", SNAPSHOTS_DIR),
    ]:
        target = Path(dir_str)
        source = staging / dir_name
        if target.exists():
            shutil.rmtree(target)
        if source.exists():
            shutil.copytree(source, target)
        else:
            target.mkdir(parents=True, exist_ok=True)

    # Ensure sources/.metadata.json exists — if missing from bundle, write empty dict
    sources_path = Path(SOURCES_DIR)
    metadata_path = sources_path / ".metadata.json"
    if sources_path.exists() and not metadata_path.exists():
        metadata_path.write_text("{}")


def _restore_template(staging: Path, wiki_config: dict) -> list:
    # Restore schema directory
    schema_target = Path(SCHEMA_DIR)
    schema_staging = staging / "schema"
    if schema_target.exists():
        shutil.rmtree(schema_target)
    if schema_staging.exists():
        shutil.copytree(schema_staging, schema_target)
    schema_target.mkdir(parents=True, exist_ok=True)

    # Remove wiki_config.json — setup wizard writes it after user confirms
    config_path = schema_target / "wiki_config.json"
    if config_path.exists():
        config_path.unlink()

    # Clear wiki, restore only _type.yaml files
    wiki_target = Path(WIKI_DIR)
    if wiki_target.exists():
        shutil.rmtree(wiki_target)
    wiki_target.mkdir(parents=True)

    wiki_staging = staging / "wiki"
    if wiki_staging.exists():
        for type_yaml in sorted(wiki_staging.rglob("_type.yaml")):
            rel = type_yaml.relative_to(wiki_staging)
            dest = wiki_target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(type_yaml, dest)

    return wiki_config.get("entity_types", [])


def _reinit_wiki_manager() -> None:
    from agent.wiki_manager import WikiManager
    try:
        wm = WikiManager(
            sources_dir=SOURCES_DIR,
            wiki_dir=WIKI_DIR,
            archive_dir=ARCHIVE_DIR,
            snapshots_dir=SNAPSHOTS_DIR,
            schema_dir=SCHEMA_DIR,
        )
        set_wiki_manager(wm)
    except Exception:
        # WikiManager may fail if LLM is not yet configured; wiki files are already
        # restored to disk. The user will configure the LLM on first use.
        pass
