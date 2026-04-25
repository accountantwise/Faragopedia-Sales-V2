# Workspace Cleanup — Design Spec

**Date:** 2026-04-25
**Status:** Approved

## Overview

Three quality-of-life improvements to workspace management:

1. A cancel affordance in the Setup Wizard when the user is adding a new workspace (not the initial first-run setup)
2. A permanent-delete action for archived workspaces, gated behind a name-confirmation modal
3. A rename action for non-archived workspaces

---

## Feature 1 — Cancel in Setup Wizard

### Behaviour

- The X button appears in the top-right corner of the wizard **only** when `onCancel` is provided as a prop.
- It is shown when the wizard is opened via the "New Workspace" flow (i.e., at least one other workspace already exists).
- It is **not** shown during the initial first-run setup (no other workspaces exist) or during the reconfigure flow.
- Clicking X calls `onCancel()` and returns the user to their previously active workspace.
- The newly created (unconfigured) workspace is **not deleted** — it remains in the workspace list so the user can finish setting it up later.

### App.tsx changes

- Add `previousActiveWorkspaceId: string` state variable, set just before calling `handleNewWorkspace()`.
- Pass `onCancel` to `SetupWizard` only when `previousActiveWorkspaceId` is set (i.e., the workspace was created via the "New Workspace" button, not the initial first-run):
  ```tsx
  onCancel={() => handleSwitchWorkspace(previousActiveWorkspaceId)}
  ```
- Initial first-run and reconfigure flows continue to receive no `onCancel`.

### SetupWizard changes

- Render an X button in the top-right when `onCancel` is defined.
- No changes to step logic or existing props.

---

## Feature 2 — Permanent Delete for Archived Workspaces

### Behaviour

- "Delete permanently" appears in the context menu only for archived workspaces.
- Clicking it opens `DeleteWorkspaceModal`.
- The modal shows a warning icon, a danger description naming the workspace, a labelled text input ("Type **{name}** to confirm"), and a "Delete forever" button.
- The "Delete forever" button is disabled until the typed value exactly matches the workspace name (case-sensitive).
- On confirm: calls `DELETE /api/workspaces/{id}`, closes the modal, and refreshes the workspace list.

### Component — `DeleteWorkspaceModal`

```tsx
interface DeleteWorkspaceModalProps {
  workspaceName: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}
```

- Loading state on the confirm button during the async call.
- Error state displayed inline if the request fails.

### WorkspaceSwitcher changes

- New `onDelete: (id: string) => Promise<void>` prop.
- "Delete permanently" context menu item renders for archived workspaces only (alongside existing "Restore").

### App.tsx changes

- Add `handleDeleteWorkspace(id: string)`: calls `DELETE /api/workspaces/{id}`, then calls `fetchWorkspaces()`.
- Pass `onDelete={handleDeleteWorkspace}` to `Sidebar` → `WorkspaceSwitcher`.

### Backend

- `DELETE /api/workspaces/{id}` already exists and already prevents deleting the active workspace. No backend changes needed.

---

## Feature 3 — Rename for Non-Archived Workspaces

### Behaviour

- "Rename" appears in the context menu for non-archived workspaces (active and inactive).
- Clicking it opens `RenameWorkspaceModal` pre-filled with the current workspace name.
- The "Rename" button is disabled when the input is empty or unchanged from the current name.
- On confirm: calls `PATCH /api/workspaces/{id}` with `{ name }`, closes the modal, and refreshes the workspace list.
- Rename changes only the display name in the workspace switcher (the registry entry). The wiki name shown in the app header comes from `wiki_config.json` and is unaffected.

### Component — `RenameWorkspaceModal`

```tsx
interface RenameWorkspaceModalProps {
  currentName: string;
  onConfirm: (name: string) => Promise<void>;
  onClose: () => void;
}
```

- Input pre-filled with `currentName`, focused on open.
- Loading state on confirm button during async call.
- Error state displayed inline if request fails.

### WorkspaceSwitcher changes

- New `onRename: (id: string, name: string) => Promise<void>` prop.
- "Rename" context menu item renders for non-archived workspaces only.

### App.tsx changes

- Add `handleRenameWorkspace(id: string, name: string)`: calls `PATCH /api/workspaces/{id}` with `{ name }`, then calls `fetchWorkspaces()`.
- Pass `onRename={handleRenameWorkspace}` to `Sidebar` → `WorkspaceSwitcher`.

### Backend — new endpoint

```
PATCH /api/workspaces/{workspace_id}
Body: { "name": "New Name" }
Response: { "id": "...", "name": "New Name", "archived": false, ... }
```

- Add `rename_workspace(workspace_id: str, name: str) -> dict` to `workspace_manager.py`.
  - Loads registry, finds workspace by id, updates `name`, saves registry, returns updated entry.
  - Workspace directories are keyed by id (slug), not name — no filesystem changes required.
- Add route in `workspace_routes.py`.

---

## Component Summary

| Component | Action | File |
|---|---|---|
| `SetupWizard` | Add X button when `onCancel` defined | existing |
| `DeleteWorkspaceModal` | New — name-confirmation delete | new file |
| `RenameWorkspaceModal` | New — prefilled name input | new file |
| `WorkspaceSwitcher` | Add Rename + Delete permanently menu items; new props | existing |
| `Sidebar` | Pass new props through to WorkspaceSwitcher | existing |
| `App` | New handlers + previousActiveWorkspaceId state | existing |
| `workspace_routes.py` | Add PATCH endpoint | existing |
| `workspace_manager.py` | Add rename_workspace() | existing |

---

## Out of Scope

- Separating the "Wiki Sitename" from the workspace name in the setup wizard (noted as future work — the wiki name shown in the app header will eventually be a fixed app-wide name, not per-workspace).
- Renaming archived workspaces.
- Deleting non-archived workspaces.
