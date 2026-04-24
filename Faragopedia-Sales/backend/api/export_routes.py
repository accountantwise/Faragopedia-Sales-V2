import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from api.routes import (
    ARCHIVE_DIR,
    SNAPSHOTS_DIR,
    SOURCES_DIR,
    WIKI_DIR,
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
async def export_bundle_full():
    manifest = {
        "version": 1,
        "type": "full",
        "exported_at": _utcnow(),
        "app_version": _APP_VERSION,
    }
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


@export_router.get("/bundle/template")
async def export_bundle_template():
    manifest = {
        "version": 1,
        "type": "template",
        "exported_at": _utcnow(),
        "app_version": _APP_VERSION,
    }
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
