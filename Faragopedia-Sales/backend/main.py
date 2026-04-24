import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router, set_wiki_manager
from api.setup_routes import setup_router
from api.export_routes import export_router
from api.workspace_routes import workspace_router
from agent.setup_wizard import is_setup_complete
from agent.workspace_manager import (
    initialize_workspaces, get_active_workspace_id,
    get_wiki_dir, get_sources_dir, get_archive_dir, get_snapshots_dir, get_schema_dir,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(setup_router, prefix="/api/setup")
app.include_router(export_router, prefix="/api/export")
app.include_router(workspace_router, prefix="/api/workspaces")

initialize_workspaces()
active_id = get_active_workspace_id()
if active_id and is_setup_complete(get_schema_dir()):
    from agent.wiki_manager import WikiManager
    wm = WikiManager(
        sources_dir=get_sources_dir(),
        wiki_dir=get_wiki_dir(),
        archive_dir=get_archive_dir(),
        snapshots_dir=get_snapshots_dir(),
        schema_dir=get_schema_dir(),
    )
    set_wiki_manager(wm)

@app.get("/")
def read_root():
    return {"message": "Hello World from FastAPI"}
