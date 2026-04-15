# Design Spec: Wiki-Concept Integration & Autonomous Agent Engine

**Date:** 2026-04-15
**Status:** Approved (Brainstorming Complete)
**Objective:** Transform Faragopedia-Sales into a production-ready knowledge engine driven by the business rules and data structure of the `Wiki-Concept` project, emulating an IDE-like autonomous agent workflow.

---

## 1. Architecture Overview

We are moving from a "Fixed Extraction" model to a "Reasoning Agent" model. The system will use an external LLM (via OpenRouter) as a central brain that interacts with the wiki filesystem through a defined set of tools.

### Components:
- **Agent Orchestrator (Backend):** A LangChain-based ReAct agent running in the FastAPI backend.
- **Toolbelt:** A set of Python functions exposed to the LLM for direct manipulation of the Wiki filesystem.
- **Context Injection:** A pre-processing layer that enforces the `SCHEMA.md` and `company_profile.md` rules.
- **Unified Storage:** The `Wiki-Concept` directory structure (clients, contacts, photographers, etc.) becomes the primary `wiki/` storage for the application.
- **Reasoning UI (Frontend):** A real-time log displaying the agent's thoughts and tool calls to provide visibility into the background process.

---

## 2. The Agent Toolbox (FileSystem Tools)

The Agent will be provided with the following tools to emulate an IDE environment:

| Tool Name | Purpose | Implementation |
|-----------|---------|----------------|
| `list_wiki_files` | Discover existing entities | Recursive `os.listdir` on the wiki directory. |
| `read_wiki_file` | Retrieve context for an entity | `open().read()` with path validation. |
| `write_wiki_file` | Create or update pages | `open().write()`. Agent provides the path (e.g., `contacts/name.md`) based on SCHEMA rules. |
| `grep_wiki` | Find relationships/mentions | `ripgrep` or Python-based regex search across all `.md` files. |
| `update_log` | Record chronological actions | Appends to `log.md` following the SCHEMA format. |

---

## 3. Data Flow & Integration

### Ingestion Protocol (The IDE Emulation):
1. **Trigger:** User uploads a source.
2. **Initialization:** Backend reads `SCHEMA.md`, `index.md`, and the last 10 entries of `log.md`.
3. **Prompt Injection:** These files are combined with the user request into a "Mission Brief" for the Agent.
4. **The Loop:**
   - Agent reads the source.
   - Agent uses `grep_wiki` to see if entities (e.g., "Louis Vuitton") already exist.
   - Agent reads relevant existing files to ensure information is merged, not overwritten.
   - Agent executes multiple `write_wiki_file` calls.
   - Agent updates `index.md` and `log.md`.
5. **Completion:** Agent returns a summary of work done.

### Storage Transition:
- The contents of `@Wiki-Concept/` will be moved into the application's `wiki/` volume.
- The backend `WikiManager` will be updated to handle the sub-directory structure (`clients/`, `contacts/`, etc.) instead of a flat file list.

---

## 4. UI & Visibility

To ensure the user isn't "left in the dark," the `Chat` and `Upload` views will be updated:
- **Streaming Thoughts:** The backend will stream the Agent's reasoning steps (e.g., *"Thinking: I need to check if Jane Doe exists in contacts..."*).
- **Action Toast:** Small notifications when a file is physically written to disk.

---

## 5. Success Criteria
- The LLM successfully categorizes new info into the correct sub-folders (`clients/`, `photographers/`, etc.).
- Cross-references are created using `[[wikilinks]]` based on actual file existence.
- The `index.md` and `log.md` are updated following the strict schema in the Wiki-Concept manual.
- No information is lost during the merge of new data into existing files.

---

## 6. Implementation Stages (Preview)
1. **Stage 1:** Consolidate `Wiki-Concept` data into the app storage.
2. **Stage 2:** Refactor `WikiManager` into a LangChain Agent loop.
3. **Stage 3:** Implement FileSystem toolbelt.
4. **Stage 4:** Update Frontend to support "Reasoning Logs."
