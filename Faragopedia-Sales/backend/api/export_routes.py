import io
import json
import os
import zipfile

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from agent.setup_wizard import SetupPayload, finalize_import
from api.routes import ARCHIVE_DIR, SNAPSHOTS_DIR, SOURCES_DIR, WIKI_DIR, set_wiki_manager

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
SCHEMA_DIR = os.path.join(_BACKEND_DIR, "schema")

export_router = APIRouter()

_BUNDLE_FILES = [
    ("schema", "SCHEMA.md"),
    ("schema", "company_profile.md"),
    ("schema", "wiki_config.json"),
    ("wiki", "index.md"),
    ("wiki", "log.md"),
]


@export_router.get("/bundle")
def export_bundle():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for source, filename in _BUNDLE_FILES:
            dir_path = SCHEMA_DIR if source == "schema" else WIKI_DIR
            full_path = os.path.join(dir_path, filename)
            if os.path.exists(full_path):
                zf.write(full_path, arcname=filename)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="wiki-bundle.zip"'},
    )


@export_router.post("/import")
async def import_bundle(file: UploadFile = File(...)):
    raw = await file.read()

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="Not a valid zip file")

    names = zf.namelist()

    if "SCHEMA.md" not in names:
        raise HTTPException(status_code=422, detail="zip must contain SCHEMA.md")
    if "wiki_config.json" not in names:
        raise HTTPException(status_code=422, detail="zip must contain wiki_config.json")

    try:
        config = json.loads(zf.read("wiki_config.json"))
    except (json.JSONDecodeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail="wiki_config.json is not valid JSON") from exc

    os.makedirs(SCHEMA_DIR, exist_ok=True)
    zf.extract("SCHEMA.md", SCHEMA_DIR)
    if "company_profile.md" in names:
        zf.extract("company_profile.md", SCHEMA_DIR)

    return {
        "wiki_name": config.get("wiki_name", ""),
        "org_name": config.get("org_name", ""),
        "org_description": config.get("org_description", ""),
        "entity_types": config.get("entity_types", []),
    }


@export_router.post("/import/finalize")
def import_finalize(payload: SetupPayload):
    from agent.wiki_manager import WikiManager

    try:
        finalize_import(SCHEMA_DIR, WIKI_DIR, payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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
        pass  # LLM may not be configured yet; wiki files are already written

    return {"success": True, "wiki_name": payload.wiki_name}
