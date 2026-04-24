from fastapi import APIRouter, HTTPException
from agent import workspace_manager
from api.routes import set_wiki_manager

workspace_router = APIRouter()


@workspace_router.get("")
def list_workspaces_endpoint():
    return {
        "workspaces": workspace_manager.list_workspaces(),
        "active_workspace_id": workspace_manager.get_active_workspace_id(),
    }


@workspace_router.post("")
def create_workspace_endpoint(payload: dict):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    result = workspace_manager.create_workspace(name)
    # result = { "id": str, "name": str, "setup_required": True }
    return result


@workspace_router.post("/{workspace_id}/switch")
def switch_workspace(workspace_id: str):
    try:
        workspace_manager.set_active_workspace(workspace_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")

    from agent.setup_wizard import is_setup_complete
    schema_dir = workspace_manager.get_schema_dir()
    if is_setup_complete(schema_dir):
        from agent.wiki_manager import WikiManager
        from agent.setup_wizard import get_wiki_config
        wm = WikiManager(
            sources_dir=workspace_manager.get_sources_dir(),
            wiki_dir=workspace_manager.get_wiki_dir(),
            archive_dir=workspace_manager.get_archive_dir(),
            snapshots_dir=workspace_manager.get_snapshots_dir(),
            schema_dir=schema_dir,
        )
        set_wiki_manager(wm)
        config = get_wiki_config(schema_dir)
        wiki_name = (config or {}).get("wiki_name", "")
        return {"id": workspace_id, "setup_required": False, "wiki_name": wiki_name}
    else:
        set_wiki_manager(None)
        return {"id": workspace_id, "setup_required": True, "wiki_name": ""}


@workspace_router.delete("/{workspace_id}")
def delete_workspace_endpoint(workspace_id: str):
    if workspace_id == workspace_manager.get_active_workspace_id():
        raise HTTPException(status_code=400, detail="Cannot delete the active workspace")
    try:
        workspace_manager.delete_workspace(workspace_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    return {"success": True}
