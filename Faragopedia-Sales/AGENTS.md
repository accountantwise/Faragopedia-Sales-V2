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
| **Phase**    | 🟡 MVP Development / Settings Section + Entity Templates planned, ready to implement |
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
| Search Engine      | Client-side JSON Index| —        |
| Linting System     | AI-powered + Snapshots| —        |
| Tagging System     | Frontmatter + Shared  | —        |
| External API Auth  | Cloudflare Access (Service Token) + backend API-key middleware | [ADR 0003](docs/decisions/0003-external-api-exposure-auth.md) |
| Link View (Graph)  | Single-pass `GET /pages/graph` + hand-rolled SVG (no graph lib) | [ADR 0005](docs/decisions/0005-link-view-graph-architecture.md) |

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
| Phase        | 🟡 MVP Development / Feature Complete                  |

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
| 15. ~~Merge `big-refactor` to `main`~~ ✅
16. ~~Execute Dynamic Folders plan~~ ✅ — all 7 tasks complete; 87 tests passing
17. ~~Merge `dynamic-folders` to `main`~~ ✅
18. ~~Execute Search & Tags plan~~ ✅ — all 8 tasks complete; 111 tests passing
19. ~~Execute Bulk Actions plan (Move, Download)~~ ✅ — 7 tasks complete; 12 tests passing
20. ~~Execute Actionable Lint system (Snapshot, Bulk Fix)~~ ✅ — 7 tasks complete; verified
21. ~~Desktop UI/UX Polish (Consistency, Layout fixes)~~ ✅
22. ~~Setup Wizard (3-step wizard, LLM schema suggestion, reconfigure flow)~~ ✅ (2026-04-21)
23. **Execute Settings Section plan (Tasks 1–13)** 👈 — spec + plan in `docs/superpowers/`; backend → Claude, frontend → Gemini
24. **Execute Entity Type Templates plan (Tasks 1–5)** — pure backend; spec + plan in `docs/superpowers/`; `main` branch
25. **Add "estimated time remaining" to Lint View**
26. **Monitor snapshot storage / add auto-pruning**
27. ~~Implement Graph View~~ ✅ (2026-07-04) — shipped as **Link View** on branch `link-view` (deployed to production): grouped-grid wikilink map (not force-directed), hover/focus connection curves, docked reading panel, content search. Backend `GET /pages/graph` builds the whole graph in one pass (ADR 0005). Verified with 35/35 browser checks in light + dark.
28. ~~Execute Web Search Sources plan (Faragopedia side)~~ ✅ (2026-05-19) — merged to `main`; 9 new tests passing; Phase 2 smoke test passed end-to-end. Wisecrawler-side `POST /v1/search` deployed with `BRAVE_API_KEY`. Known limitation: JS-rendered/auth-gated URLs (LinkedIn, paywalled sites) fail at Wisecrawler's analyze step — pre-existing crawler behaviour, not a web-search bug.
29. ~~Author + critically review a 10-point growth roadmap~~ ✅ (2026-07-08) — production hardening, security remediation, auth, permissions/sharing, admin dashboard, routing/frontend refactor, version history, collaboration, semantic search/RAG, UX polish. Docs live in `roadmap/` at the repo root (sibling to this folder, not inside it); verdicts and evidence in `roadmap/00-review-log.md`. All 10 approved for build; sequencing in `roadmap/00-overview.md` — **01 (production hardening) and 02 (security remediation) are next**, since prod currently runs the dev server with no auth. Hand each doc to a build session one at a time.



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
