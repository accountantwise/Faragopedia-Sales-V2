from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
import os
import shutil
import re
import asyncio
from agent.wiki_manager import WikiManager

router = APIRouter()

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

def secure_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal.
    Used for uploaded files where the name comes from untrusted user input.
    """
    filename = os.path.basename(filename)
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    return filename

def safe_wiki_filename(filename: str) -> str:
    """
    Validate a wiki page filename for safe lookup.
    Strips directory components and enforces .md extension without
    mangling the characters that _get_page_path preserves (parentheses, +, etc.).
    """
    filename = os.path.basename(filename)
    if not filename.endswith(".md"):
        raise ValueError(f"Invalid page filename: {filename!r} — must end with .md")
    
    wiki_real = os.path.realpath(WIKI_DIR)
    resolved = os.path.realpath(os.path.join(wiki_real, filename))
    
    # On Windows, paths are case-insensitive
    if os.name == 'nt':
        if not (resolved.lower() == wiki_real.lower() or resolved.lower().startswith(wiki_real.lower() + os.sep)):
            raise ValueError("Path traversal detected")
    else:
        if not (resolved == wiki_real or resolved.startswith(wiki_real + os.sep)):
            raise ValueError("Path traversal detected")
            
    return filename

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), ingest: bool = Query(True)):
    print(f"DEBUG: Starting upload for file: {file.filename}, ingest: {ingest}")
    # Robust directory checking
    if not os.path.exists(SOURCES_DIR):
        try:
            print(f"DEBUG: Creating SOURCES_DIR: {SOURCES_DIR}")
            os.makedirs(SOURCES_DIR, exist_ok=True)
        except Exception as e:
            print(f"DEBUG: Error creating sources directory: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Could not create sources directory: {str(e)}")
    
    # Check if directory is writeable
    if not os.access(SOURCES_DIR, os.W_OK):
        print(f"DEBUG: Sources directory not writeable: {SOURCES_DIR}")
        raise HTTPException(status_code=500, detail="Sources directory is not writeable")

    # Sanitize filename
    safe_filename = secure_filename(file.filename)
    file_path = os.path.join(SOURCES_DIR, safe_filename)
    print(f"DEBUG: Saving file to: {file_path}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"DEBUG: File saved successfully: {file_path}")
    except Exception as e:
        print(f"DEBUG: Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
    
    # Trigger ingestion in the background if requested
    if ingest:
        print(f"DEBUG: Triggering ingestion for: {safe_filename}")
        asyncio.create_task(wiki_manager.ingest_source(safe_filename))
        message = "File uploaded and ingestion started"
    else:
        print(f"DEBUG: Skipping immediate ingestion for: {safe_filename}")
        message = "File uploaded successfully (ingestion skipped)"
    
    return {"filename": safe_filename, "message": message}

@router.post("/chat")
async def chat(query: str):
    if not query:
        raise HTTPException(status_code=422, detail="Query parameter is required")
    
    try:
        response = await wiki_manager.query(query)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@router.get("/health")
async def health_check():
    try:
        return wiki_manager.health_check()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing health check: {str(e)}")

@router.get("/pages")
async def list_pages():
    try:
        return wiki_manager.list_pages()
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

@router.get("/pages/{filename}")
async def get_page(filename: str):
    try:
        safe_name = safe_wiki_filename(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return {"content": wiki_manager.get_page_content(safe_name)}
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

@router.get("/pages/{filename}/backlinks")
async def get_backlinks(filename: str):
    try:
        safe_name = safe_wiki_filename(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return wiki_manager.get_backlinks(safe_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching backlinks: {str(e)}")

@router.post("/pages")
async def create_page():
    try:
        filename = await wiki_manager.create_new_page()
        return {"filename": filename, "message": "New page created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating page: {str(e)}")

@router.delete("/pages/{filename}")
async def delete_page(filename: str):
    try:
        safe_name = safe_wiki_filename(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await wiki_manager.archive_page(safe_name)
        return {"message": "Page moved to archive"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception as e:
        import traceback
        traceback.print_exc()
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

@router.post("/archive/pages/{filename}/restore")
async def restore_page(filename: str):
    try:
        # Basic basename check for archive files
        safe_name = os.path.basename(filename)
        await wiki_manager.restore_page(safe_name)
        return {"message": "Page restored from archive"}
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

@router.delete("/archive/pages/{filename}/permanent")
async def delete_archived_page_permanent(filename: str):
    try:
        safe_name = os.path.basename(filename)
        await wiki_manager.delete_archived_page(safe_name)
        return {"message": "Page permanently deleted from archive"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archived page not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting page: {str(e)}")

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

@router.get("/pages/{filename}/download")
async def download_page(filename: str):
    try:
        safe_name = safe_wiki_filename(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    path = os.path.join(WIKI_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(path, filename=safe_name, media_type="text/markdown")

@router.get("/sources/{filename}/download")
async def download_source(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(SOURCES_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Source not found")
    return FileResponse(path, filename=safe_name)

@router.put("/pages/{filename}")
async def update_page(filename: str, payload: dict):
    try:
        safe_name = safe_wiki_filename(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    content = payload.get("content")
    if content is None:
        raise HTTPException(status_code=422, detail="Content is required")
        
    try:
        await wiki_manager.save_page_content(safe_name, content)
        return {"message": "Page updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating page: {str(e)}")
