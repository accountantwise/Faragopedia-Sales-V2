import os
import shutil

from fastapi import APIRouter, HTTPException

from agent.setup_wizard import (
    EntityTypeDefinition,  # noqa: F401 — re-exported for tests
    EntityTypeField,  # noqa: F401
    SetupPayload,
    SuggestRequest,
    SuggestedSchema,  # noqa: F401
    clear_setup,
    complete_setup,
    get_wiki_config,
    is_setup_complete,
    suggest_schema_llm,
)
from api.routes import (
    ARCHIVE_DIR,
    SNAPSHOTS_DIR,
    SOURCES_DIR,
    WIKI_DIR,
    set_wiki_manager,
)

setup_router = APIRouter()

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))   # backend/api/
_BACKEND_DIR = os.path.dirname(_THIS_DIR)                 # backend/
SCHEMA_DIR = os.path.join(_BACKEND_DIR, "schema")


@setup_router.get("/status")
def setup_status():
    config = get_wiki_config(SCHEMA_DIR)
    if config and config.get("setup_complete"):
        return {"setup_required": False, "wiki_name": config.get("wiki_name", "")}
    return {"setup_required": True}


@setup_router.get("/config")
def setup_config():
    config = get_wiki_config(SCHEMA_DIR)
    if not config:
        raise HTTPException(status_code=404, detail="Wiki not configured")
    return {"wiki_name": config.get("wiki_name", ""), "org_name": config.get("org_name", "")}


@setup_router.post("/suggest-schema")
def suggest_schema(req: SuggestRequest):
    try:
        from agent.wiki_manager import WikiManager
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WikiManager(
                sources_dir=tmpdir,
                wiki_dir=tmpdir,
                archive_dir=tmpdir,
                snapshots_dir=tmpdir,
                schema_dir=tmpdir,
            )
            llm = wm._init_llm()
        result = suggest_schema_llm(req.org_name, req.org_description, llm)
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="LLM unavailable") from exc


@setup_router.post("/complete")
def setup_complete(payload: SetupPayload):
    try:
        from agent.wiki_manager import WikiManager
        complete_setup(SCHEMA_DIR, WIKI_DIR, payload)
        wm = WikiManager(
            sources_dir=SOURCES_DIR,
            wiki_dir=WIKI_DIR,
            archive_dir=ARCHIVE_DIR,
            snapshots_dir=SNAPSHOTS_DIR,
            schema_dir=SCHEMA_DIR,
        )
        set_wiki_manager(wm)
        return {"success": True, "wiki_name": payload.wiki_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@setup_router.post("/clear")
def setup_clear():
    set_wiki_manager(None)
    folders = clear_setup(SCHEMA_DIR, WIKI_DIR)
    return {"existing_folders": folders}


@setup_router.delete("/folder/{folder_name}")
def delete_setup_folder(folder_name: str):
    import re
    if not re.match(r"^[a-z][a-z0-9-]*$", folder_name):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    folder_path = os.path.join(WIKI_DIR, folder_name)
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Folder not found")
    shutil.rmtree(folder_path)
    return {"success": True}
