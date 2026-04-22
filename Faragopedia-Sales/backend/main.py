import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router, set_wiki_manager, WIKI_DIR, SOURCES_DIR, ARCHIVE_DIR, SNAPSHOTS_DIR
from api.setup_routes import setup_router, SCHEMA_DIR
from api.export_routes import export_router
from agent.setup_wizard import migrate_existing, is_setup_complete

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

migrate_existing(SCHEMA_DIR)
if is_setup_complete(SCHEMA_DIR):
    from agent.wiki_manager import WikiManager
    wm = WikiManager(
        sources_dir=SOURCES_DIR,
        wiki_dir=WIKI_DIR,
        archive_dir=ARCHIVE_DIR,
        snapshots_dir=SNAPSHOTS_DIR,
        schema_dir=SCHEMA_DIR,
    )
    set_wiki_manager(wm)

@app.get("/")
def read_root():
    return {"message": "Hello World from FastAPI"}
