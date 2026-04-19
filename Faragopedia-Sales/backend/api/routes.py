from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks
from datetime import datetime
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import os
import json
import shutil
import re
import asyncio
from typing import Dict, List
from agent.wiki_manager import WikiManager

router = APIRouter()

class TagsUpdate(BaseModel):
    tags: List[str]

class BulkFilenames(BaseModel):
    filenames: List[str]

class BulkPaths(BaseModel):
    paths: List[str]

class BulkMove(BaseModel):
    paths: List[str]
    destination: str

# The 'sources/' directory is at '../sources' from 'backend/' if running inside the container,
# or './sources' from the root.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# If we are in the 'backend' directory (common in local dev), the project root is one level up.
if os.path.basename(BASE_DIR) == "backend":
    BASE_DIR = os.path.dirname(BASE_DIR)

SOURCES_DIR = os.path.join(BASE_DIR, "sources")
WIKI_DIR = os.path.join(BASE_DIR, "wiki")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")

# Instantiate WikiManager
wiki_manager = WikiManager(
    sources_dir=SOURCES_DIR,
    wiki_dir=WIKI_DIR,
    archive_dir=ARCHIVE_DIR
)

def get_valid_entity_subdirs() -> set:
    """Get valid entity subdirectories dynamically from wiki_manager."""
    return set(wiki_manager.get_entity_types().keys())

def rewrite_wikilinks(path_map: dict) -> dict:
    """Scan all .md files in WIKI_DIR and rewrite wikilinks for moved pages.

    path_map: {old_path: new_path} e.g. {"prospects/acme.md": "clients/acme.md"}
    Returns: {file_path: count_of_rewrites}
    """
    links_rewritten = {}
    for root, dirs, files in os.walk(WIKI_DIR):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            full = os.path.join(root, fname)
            try:
                with open(full, "r", encoding="utf-8") as f:
                    original = f.read()
            except OSError:
                continue
            updated = original
            count = 0
            for old_path, new_path in path_map.items():
                # Strip .md for wikilink format: [[subdir/page-name]]
                old_link = old_path[:-3] if old_path.endswith(".md") else old_path
                new_link = new_path[:-3] if new_path.endswith(".md") else new_path
                pattern = r'\[\[' + re.escape(old_link) + r'\]\]'
                replacement = f'[[{new_link}]]'
                new_text, n = re.subn(pattern, replacement, updated)
                updated = new_text
                count += n
            if count > 0 and updated != original:
                with open(full, "w", encoding="utf-8") as f:
                    f.write(updated)
                # Use relative path from WIKI_DIR for the key
                rel = os.path.relpath(full, WIKI_DIR).replace("\\", "/")
                links_rewritten[rel] = count
    return links_rewritten

def secure_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal.
    Used for uploaded files where the name comes from untrusted user input.
    """
    filename = os.path.basename(filename)
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    return filename

def safe_wiki_filename(path: str) -> str:
    """Validate a wiki page path of the form 'subdir/page-name.md'.
    Accepts exactly one level of subdirectory from VALID_ENTITY_SUBDIRS.
    Rejects path traversal, unknown subdirectories, and non-.md files.
    """
    # Normalize separators
    normalized = path.replace("\\", "/")

    # Must end with .md
    if not normalized.endswith(".md"):
        raise ValueError(f"Invalid page path: {path!r} — must end with .md")

    parts = normalized.split("/")

    # Must be exactly subdir/filename.md (2 parts)
    if len(parts) != 2:
        raise ValueError(f"Invalid entity subdirectory in path: {path!r}")

    subdir, filename = parts

    # Subdir must be a known entity type
    if subdir not in get_valid_entity_subdirs():
        raise ValueError(f"Invalid entity subdirectory '{subdir}' in path: {path!r}")

    # No path traversal components
    if ".." in filename or ".." in subdir:
        raise ValueError(f"Path traversal detected in: {path!r}")

    # Validate the full resolved path stays within wiki dir
    wiki_real = os.path.realpath(WIKI_DIR)
    resolved = os.path.realpath(os.path.join(wiki_real, subdir, filename))

    if os.name == "nt":
        if not resolved.lower().startswith(wiki_real.lower() + os.sep):
            raise ValueError(f"Path traversal detected in: {path!r}")
    else:
        if not resolved.startswith(wiki_real + os.sep):
            raise ValueError(f"Path traversal detected in: {path!r}")

    return normalized

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), ingest: bool = Query(True)):
    if not os.path.exists(SOURCES_DIR):
        try:
            os.makedirs(SOURCES_DIR, exist_ok=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not create sources directory: {str(e)}")

    if not os.access(SOURCES_DIR, os.W_OK):
        raise HTTPException(status_code=500, detail="Sources directory is not writeable")

    safe_filename = secure_filename(file.filename)
    file_path = os.path.join(SOURCES_DIR, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

    if ingest:
        asyncio.create_task(wiki_manager.ingest_source(safe_filename))
        message = "File uploaded and ingestion started"
    else:
        message = "File uploaded successfully (ingestion skipped)"

    return {"filename": safe_filename, "message": message}

@router.post("/paste")
async def paste_source(payload: dict):
    content = payload.get("content", "")
    if not content or not content.strip():
        raise HTTPException(status_code=422, detail="Content is required")

    name = (payload.get("name") or "").strip()
    if name:
        filename = secure_filename(name)
        if not filename.endswith(".txt"):
            filename += ".txt"
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"paste-{timestamp}.txt"

    os.makedirs(SOURCES_DIR, exist_ok=True)
    file_path = os.path.join(SOURCES_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {"filename": filename, "message": "Text saved as source"}


@router.post("/chat")
async def chat(query: str):
    if not query or not query.strip():
        raise HTTPException(status_code=422, detail="Query parameter is required")
    
    try:
        response = await wiki_manager.query(query)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@router.get("/pages")
async def list_pages():
    """Return wiki pages grouped by entity subdirectory."""
    try:
        all_pages = wiki_manager.list_pages()
        valid_subdirs = get_valid_entity_subdirs()
        grouped: Dict[str, List[str]] = {sub: [] for sub in valid_subdirs}
        for page_path in all_pages:
            parts = page_path.split("/")
            if len(parts) == 2 and parts[0] in valid_subdirs:
                grouped[parts[0]].append(page_path)
        return grouped
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing pages: {str(e)}")

@router.get("/sources")
async def list_sources():
    try:
        return wiki_manager.list_sources()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing sources: {str(e)}")

@router.get("/sources/metadata")
async def get_sources_metadata():
    try:
        return wiki_manager.get_sources_metadata()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching source metadata: {str(e)}")

@router.post("/sources/{filename}/ingest")
async def ingest_source(filename: str):
    try:
        # We use secure_filename to avoid traversal
        safe_name = os.path.basename(filename)
        # Check if file exists in sources
        if not os.path.exists(os.path.join(SOURCES_DIR, safe_name)):
            raise FileNotFoundError("Source file not found")
            
        asyncio.create_task(wiki_manager.ingest_source(safe_name))
        return {"message": f"Ingestion started for {safe_name}"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting ingestion: {str(e)}")

@router.post("/sources/bulk-ingest")
async def bulk_ingest_sources(payload: BulkFilenames):
    queued = []
    skipped = []
    for filename in payload.filenames:
        safe_name = os.path.basename(filename)
        if os.path.exists(os.path.join(SOURCES_DIR, safe_name)):
            asyncio.create_task(wiki_manager.ingest_source(safe_name))
            queued.append(safe_name)
        else:
            skipped.append(safe_name)
    return JSONResponse(status_code=202, content={"queued": queued, "skipped": skipped})

@router.get("/pages/{path:path}/backlinks")
async def get_backlinks(path: str):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return wiki_manager.get_backlinks(safe_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching backlinks: {str(e)}")


@router.get("/pages/{path:path}/download")
async def download_page(path: str):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    full_path = os.path.join(WIKI_DIR, safe_path.replace("/", os.sep))
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Page not found")
    filename = safe_path.split("/")[-1]
    return FileResponse(full_path, filename=filename, media_type="text/markdown")


@router.get("/pages/{path:path}")
async def get_page(path: str):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return {"content": wiki_manager.get_page_content(safe_path)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading page: {str(e)}")


@router.get("/sources/{filename}")
async def get_source(filename: str):
    try:
        # We use secure_filename to avoid traversal but still let the user browse the source files
        safe_name = os.path.basename(filename)
        return {"content": await wiki_manager.get_source_content(safe_name)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading source: {str(e)}")


@router.post("/pages")
async def create_page(entity_type: str = Query("clients")):
    if entity_type not in get_valid_entity_subdirs():
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")
    try:
        filename = await wiki_manager.create_new_page(entity_type=entity_type)
        return {"filename": filename, "message": "New page created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating page: {str(e)}")


@router.get("/entity-types")
async def get_entity_types():
    try:
        return wiki_manager.get_entity_types()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing entity types: {str(e)}")


@router.post("/folders")
async def create_folder(payload: dict):
    name = payload.get("name", "").strip()
    display_name = payload.get("display_name", "").strip()
    description = payload.get("description", "").strip()
    if not name or not display_name:
        raise HTTPException(status_code=422, detail="name and display_name are required")
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        raise HTTPException(status_code=400, detail="Folder name must be lowercase alphanumeric with hyphens")
    try:
        await wiki_manager.create_folder(name, display_name, description)
        return {"message": f"Folder '{name}' created", "folder": name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating folder: {str(e)}")


@router.delete("/folders/{folder_name}")
async def delete_folder(folder_name: str):
    try:
        await wiki_manager.delete_folder(folder_name)
        return {"message": f"Folder '{folder_name}' deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting folder: {str(e)}")


@router.put("/folders/{folder_name}")
async def rename_folder(folder_name: str, payload: dict):
    new_name = payload.get("new_name", "").strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="new_name is required")
    if not re.match(r"^[a-z][a-z0-9-]*$", new_name):
        raise HTTPException(status_code=400, detail="Folder name must be lowercase alphanumeric with hyphens")
    try:
        await wiki_manager.rename_folder(folder_name, new_name)
        return {"message": f"Folder renamed: {folder_name} → {new_name}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error renaming folder: {str(e)}")


@router.post("/pages/{path:path}/move")
async def move_page(path: str, payload: dict):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    target_folder = payload.get("target_folder", "").strip()
    if not target_folder:
        raise HTTPException(status_code=422, detail="target_folder is required")
    try:
        new_path = await wiki_manager.move_page(safe_path, target_folder)
        return {"message": f"Page moved to {new_path}", "new_path": new_path}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error moving page: {str(e)}")


@router.post("/lint")
async def run_lint():
    try:
        report = await wiki_manager.lint()
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running lint: {str(e)}")


@router.delete("/sources/bulk")
async def bulk_archive_sources(payload: BulkFilenames):
    archived = []
    errors = []
    for filename in payload.filenames:
        safe_name = os.path.basename(filename)
        try:
            await wiki_manager.archive_source(safe_name)
            archived.append(safe_name)
        except Exception:
            errors.append(safe_name)
    return {"archived": archived, "errors": errors}


@router.delete("/pages/bulk")
async def bulk_archive_pages(payload: BulkPaths):
    archived = []
    errors = []
    for path in payload.paths:
        try:
            safe_path = safe_wiki_filename(path)
            await wiki_manager.archive_page(safe_path)
            archived.append(path)
        except Exception:
            errors.append(path)
    return {"archived": archived, "errors": errors}


@router.post("/pages/bulk-move")
async def bulk_move_pages(payload: BulkMove):
    valid_destinations = get_valid_entity_subdirs()
    if payload.destination not in valid_destinations:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid destination '{payload.destination}'. Must be one of: {sorted(valid_destinations)}"
        )
    moved = []
    errors = []
    path_map = {}
    for path in payload.paths:
        try:
            safe_path = safe_wiki_filename(path)
        except ValueError as e:
            errors.append({"path": path, "error": str(e)})
            continue
        filename = safe_path.split("/")[1]  # e.g. "acme.md"
        new_path = f"{payload.destination}/{filename}"
        src = os.path.join(WIKI_DIR, safe_path.replace("/", os.sep))
        dst = os.path.join(WIKI_DIR, new_path.replace("/", os.sep))
        if os.path.exists(dst):
            errors.append({"path": path, "error": "destination already exists"})
            continue
        try:
            os.rename(src, dst)
            moved.append(f"{safe_path} → {new_path}")
            path_map[safe_path] = new_path
        except OSError as e:
            errors.append({"path": path, "error": str(e)})
    links_rewritten = rewrite_wikilinks(path_map) if path_map else {}
    return {"moved": moved, "errors": errors, "links_rewritten": links_rewritten}


@router.delete("/pages/{path:path}")
async def delete_page(path: str):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await wiki_manager.archive_page(safe_path)
        return {"message": "Page moved to archive"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error archiving page: {str(e)}")

@router.delete("/sources/{filename}")
async def delete_source(filename: str):
    try:
        safe_name = os.path.basename(filename)
        await wiki_manager.archive_source(safe_name)
        return {"message": "Source moved to archive"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error archiving source: {str(e)}")

@router.get("/archive/pages")
async def list_archived_pages():
    try:
        return wiki_manager.list_archived_pages()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing archived pages: {str(e)}")

@router.get("/archive/sources")
async def list_archived_sources():
    try:
        return wiki_manager.list_archived_sources()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing archived sources: {str(e)}")

@router.post("/archive/pages/{filename:path}/restore")
async def restore_page(filename: str):
    try:
        safe_name = safe_wiki_filename(filename)
        await wiki_manager.restore_page(safe_name)
        return {"message": "Page restored from archive"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archived page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring page: {str(e)}")

@router.post("/archive/sources/{filename}/restore")
async def restore_source(filename: str):
    try:
        safe_name = os.path.basename(filename)
        await wiki_manager.restore_source(safe_name)
        return {"message": "Source restored from archive"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archived source not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring source: {str(e)}")

@router.delete("/archive/pages/{filename:path}/permanent")
async def delete_archived_page_permanent(filename: str):
    try:
        safe_name = safe_wiki_filename(filename)
        await wiki_manager.delete_archived_page(safe_name)
        return {"message": "Page permanently deleted from archive"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archived page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting page: {str(e)}")

# ── URL scraping via WiseCrawler ──────────────────────────────────────────────

async def _crawl_and_save(url: str) -> None:
    """Background task: crawl a URL with WiseCrawler, analyze, save to sources/."""
    import logging
    from urllib.parse import urlparse
    from agent.wisecrawler import start_crawl, poll_until_done, analyze_crawl, DEFAULT_ANALYZE_PROMPT

    logger = logging.getLogger(__name__)
    try:
        job_id = await start_crawl(url)
        await poll_until_done(job_id)
        analysis = await analyze_crawl(job_id, DEFAULT_ANALYZE_PROMPT)

        parsed = urlparse(url)
        domain = parsed.netloc.replace(".", "-").replace(":", "-")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{domain}-{timestamp}.md"

        os.makedirs(SOURCES_DIR, exist_ok=True)
        file_path = os.path.join(SOURCES_DIR, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# Source: {url}\n\n{analysis}")

        logger.info(f"Saved crawl result for {url} → {filename}")
    except Exception as exc:
        logger.error(f"Failed to crawl {url}: {exc}")


@router.post("/scrape-urls", status_code=202)
async def scrape_urls(payload: dict, background_tasks: BackgroundTasks):
    base_url = os.getenv("WISECRAWLER_BASE_URL", "")
    if not base_url:
        raise HTTPException(status_code=503, detail="WISECRAWLER_BASE_URL is not configured")

    urls = payload.get("urls", [])
    if not urls:
        raise HTTPException(status_code=422, detail="urls list is required and cannot be empty")

    for url in urls:
        background_tasks.add_task(_crawl_and_save, url)

    return {"message": f"Started {len(urls)} crawl job(s)"}


@router.delete("/archive/sources/{filename}/permanent")
async def delete_archived_source_permanent(filename: str):
    try:
        safe_name = os.path.basename(filename)
        await wiki_manager.delete_archived_source(safe_name)
        return {"message": "Source permanently deleted from archive"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archived source not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting source: {str(e)}")

@router.get("/sources/{filename}/download")
async def download_source(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(SOURCES_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Source not found")
    return FileResponse(path, filename=safe_name)

@router.get("/search/index")
async def get_search_index():
    index_path = os.path.join(WIKI_DIR, "search-index.json")
    if not os.path.exists(index_path):
        wiki_manager._rebuild_search_index()
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading search index: {str(e)}")


@router.get("/tags")
async def get_tags():
    index_path = os.path.join(WIKI_DIR, "search-index.json")
    if not os.path.exists(index_path):
        wiki_manager._rebuild_search_index()
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        tag_counts: dict[str, int] = {}
        for page in index.get("pages", []):
            for t in page.get("tags", []):
                tag_counts[t] = tag_counts.get(t, 0) + 1
        for src in index.get("sources", []):
            for t in src.get("tags", []):
                tag_counts[t] = tag_counts.get(t, 0) + 1
        return tag_counts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading tags: {str(e)}")


@router.patch("/pages/{path:path}/tags")
async def update_page_tags(path: str, body: TagsUpdate):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await wiki_manager.update_page_tags(safe_path, body.tags)
        return {"tags": body.tags}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating tags: {str(e)}")


@router.patch("/sources/{filename}/tags")
async def update_source_tags(filename: str, body: TagsUpdate):
    safe_name = os.path.basename(filename)
    src_path = os.path.join(SOURCES_DIR, safe_name)
    if not os.path.exists(src_path):
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        wiki_manager.update_source_tags(safe_name, body.tags)
        return {"tags": body.tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating source tags: {str(e)}")


@router.post("/search/rebuild")
async def rebuild_search_index():
    try:
        wiki_manager._rebuild_search_index()
        return {"message": "Search index rebuilt"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rebuilding index: {str(e)}")


@router.put("/pages/{path:path}")
async def update_page(path: str, payload: dict):
    try:
        safe_path = safe_wiki_filename(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    content = payload.get("content")
    if content is None:
        raise HTTPException(status_code=422, detail="Content is required")
    try:
        suggested_tags = await wiki_manager.save_page_content(safe_path, content)
        return {"message": "Page updated successfully", "suggested_tags": suggested_tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating page: {str(e)}")
