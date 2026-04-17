# AGENTS.md — Single Source of Truth

> **This file is the shared context for ALL AI agents working on this project.**
> Both `CLAUDE.md` and `GEMINI.md` point here. Any agent-agnostic context,
> conventions, decisions, and project state should live in this file or in the
> `docs/` directory it references.

---

## Project Identity

| Field        | Value                                                    |
| ------------ | -------------------------------------------------------- |
| **Name**     | Faragopedia-Sales                                        |
| **Repo**     | `github.com/accountantwise/Faragopedia-Sales`            |
| **Phase**    | 🟡 MVP Development / Prototype Complete                  |
| **Stack**    | Python/FastAPI + React/Vite                              |
| **Deploy**   | Docker container → Portainer on Ubuntu server            |

## Project Vision

Faragopedia-Sales is a ground-up redesign of the original Faragopedia project (a
Wikinote-taking application). The final shape of this project is still being
explored. As decisions are made, they will be recorded in
[`docs/decisions/`](docs/decisions/) and this file will be updated to reflect the
current direction.

### Relationship to Original Faragopedia

- The original project was a Wikinote-taking app with graph-based navigation.
- This project is a **full redesign**, not a fork or incremental update.
- Design learnings from the original should inform — but not constrain — this build.

---

## Architecture & Stack Decisions

| Decision           | Status               | ADR Link |
| ------------------ | -------------------- | -------- |
| Frontend framework | React (Vite)         | —        |
| Backend framework  | FastAPI              | —        |
| AI Framework       | LangChain            | —        |
| Multi-Model Support| OpenAI, Anthropic, Gemini, OpenRouter | —        |
| Database           | File-based (Wiki MD) | —        |
| File Management    | Archive/Trash System | [ADR 0001](docs/decisions/0001-file-management-and-ingestion.md) |

---

## Coding Conventions

### General

- Use clear, descriptive names for files, functions, and variables.
- Prefer small, focused files over monolithic ones.
- Write comments for **why**, not **what**.
- **LLM Wiki Specifics**: Follow the `methodology.md` rules for `index.md`, `log.md`, and page linking.

### Git Workflow

- `main` branch is the deployment branch.
- Feature work happens on feature branches: `feature/<short-description>`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `type(scope): description` (e.g., `feat(ui): add sidebar navigation`).

### Documentation

- Architecture decisions → `docs/decisions/NNNN-title.md` (ADR format).
- Living project status → `docs/status.md`.
- Agent context → this file (`AGENTS.md`).

---

## Current Status

> See [`docs/status.md`](docs/status.md) for the detailed living status document.
| Phase        | 🟡 MVP Development / Prototype Functional              |

...

### Immediate Priorities

1. ~~Initialize project scaffold with shared AI context~~ ✅
2. ~~Implement functional LLM Wiki Prototype with Multi-Provider Support~~ ✅
3. ~~Resolve port conflicts and set up local development workflow~~ ✅
4. ~~Implement interactive [[WikiLinks]] in the frontend~~ ✅
5. ~~Fix ingestion race conditions~~ ✅
6. ~~Implement Backlinks/Linked Mentions~~ ✅
7. ~~Implement Navigation History (back/forward)~~ ✅
8. ~~Add Edit Page capability~~ ✅
9. ~~Implement Sources View (Browse/Read raw data)~~ ✅
10. ~~Implement File Management (Archive, Restore, Delete, Download)~~ ✅
11. ~~Improve Source Ingestion (Manual control, Status tracking)~~ ✅
12. ~~Refine AI maintenance logic (semantic linting)~~ → Superseded by Wiki-Concept Integration
13. ~~Execute Wiki-Concept Integration Plan~~ ✅ — All 12 tasks complete on `big-refactor`; see `docs/superpowers/plans/2026-04-15-wiki-integration-claude.md`
14. ~~Create GitHub repository and push initial commit~~ ✅
15. **Merge `big-refactor` to `main`** 👈
16. ~~Execute Dynamic Folders plan~~ ✅ — all 7 tasks complete on `dynamic-folders` branch; 87 tests passing
17. **Merge `dynamic-folders` to `main`**


---

## Deployment

### Target Environment

- **Host:** Ubuntu server (remote machine)
- **Orchestration:** Portainer
- **Workflow:** Push to GitHub → Import repo as Portainer stack → Deploy container
- **Container:** Docker (base image TBD with stack)

### Files

- `Dockerfile` — container build instructions (skeleton for now)
- `docker-compose.yml` — service definitions for Portainer stack import

---

## Agent Collaboration Protocol

### Shared Context Model

```
AGENTS.md          ← You are here. The single source of truth.
├── docs/
│   ├── status.md       ← Living project status
│   └── decisions/      ← Architecture Decision Records (ADRs)
├── CLAUDE.md           ← Claude-specific overrides, points here
└── GEMINI.md           ← Gemini-specific overrides, points here
```

### Rules for AI Agents

1. **Read `AGENTS.md` first** at the start of every session.
2. **Check `docs/status.md`** to understand what has been done and what is in
   progress.
3. **Record decisions** — if you make an architectural or stack choice, create an
   ADR in `docs/decisions/` and update the table above.
4. **Update `docs/status.md`** at the end of any session where meaningful work
   was done.
5. **Do not duplicate context** — agent-specific files (`CLAUDE.md`, `GEMINI.md`)
   should only contain agent-specific configuration, not project context.
6. **Prefer this file** over agent-specific memory systems for anything another
   agent would need to know.
