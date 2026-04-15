# Ingestion Race Condition Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent data corruption in `index.md`, `log.md`, and entity pages when multiple users upload files simultaneously.

**Architecture:** Add a single `asyncio.Lock` to `WikiManager`. `ingest_source` is split into two phases — the slow LLM call runs freely (concurrent), and the file-write section acquires the lock (serialized). No new dependencies.

**Tech Stack:** Python asyncio, pytest, pytest-asyncio

---

## File Map

| File | What changes |
|------|-------------|
| `backend/agent/wiki_manager.py` | Add `import asyncio`; add `self._write_lock`; restructure `ingest_source` into two phases |
| `backend/tests/test_wiki_manager.py` | Add `import asyncio`; add lock presence test and concurrent ingestion correctness test |

---

## Task 1: Serialize file writes with asyncio.Lock

**Files:**
- Modify: `backend/agent/wiki_manager.py:1-10` (import), `backend/agent/wiki_manager.py:22-33` (`__init__`), `backend/agent/wiki_manager.py:85-125` (`ingest_source`)
- Test: `backend/tests/test_wiki_manager.py`

---

- [ ] **Step 1: Write the failing tests**

Add `import asyncio` to the imports block at the **top** of `backend/tests/test_wiki_manager.py`:

```python
import asyncio
```

Then add the following two tests at the **bottom** of the file:

```python
def test_wiki_manager_has_write_lock(temp_dirs):
    """_write_lock must exist and be an asyncio.Lock."""
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)
    assert hasattr(manager, '_write_lock')
    assert isinstance(manager._write_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_concurrent_ingestion_no_corruption(temp_dirs):
    """Two simultaneous ingestions must both appear in index.md and log.md."""
    sources, wiki = temp_dirs
    manager = WikiManager(sources_dir=sources, wiki_dir=wiki)

    # Create two source files
    for name in ["alpha.txt", "beta.txt"]:
        with open(os.path.join(sources, name), "w", encoding="utf-8") as f:
            f.write(f"Content of {name}")

    mock_result_alpha = IngestionResult(
        source_summary="Summary of alpha.",
        entities=[Entity(name="AlphaEntity", summary="Alpha summary", details="Alpha details")]
    )
    mock_result_beta = IngestionResult(
        source_summary="Summary of beta.",
        entities=[Entity(name="BetaEntity", summary="Beta summary", details="Beta details")]
    )

    call_results = [mock_result_alpha, mock_result_beta]
    call_count = [0]

    async def mock_ainvoke(_data):
        # Yield to event loop so both coroutines reach the LLM phase before
        # either proceeds to file writes — exercises the lock under contention.
        await asyncio.sleep(0)
        result = call_results[call_count[0] % 2]
        call_count[0] += 1
        return result

    with patch("agent.wiki_manager.PromptTemplate", autospec=True) as mock_prompt, \
         patch("agent.wiki_manager.PydanticOutputParser", autospec=True):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = mock_ainvoke
        mock_prompt.return_value.__or__.return_value.__or__.return_value = mock_chain

        await asyncio.gather(
            manager.ingest_source("alpha.txt"),
            manager.ingest_source("beta.txt"),
        )

    index_path = os.path.join(wiki, "index.md")
    with open(index_path, "r", encoding="utf-8") as f:
        index_content = f.read()

    assert "[[AlphaEntity]]" in index_content, "AlphaEntity missing from index.md"
    assert "[[BetaEntity]]" in index_content, "BetaEntity missing from index.md"

    log_path = os.path.join(wiki, "log.md")
    with open(log_path, "r", encoding="utf-8") as f:
        log_content = f.read()

    assert log_content.count("Processed") == 2, "Expected 2 log entries, got fewer"
```

- [ ] **Step 2: Run the tests to confirm the first one fails**

Run from the project root:
```bash
cd "C:\Users\Colacho\Nextcloud\AI\VS Code\Faragopedia\Faragopedia-Sales"
python -m pytest backend/tests/test_wiki_manager.py -v -k "write_lock or concurrent"
```
Expected:
```
FAILED backend/tests/test_wiki_manager.py::test_wiki_manager_has_write_lock
  AssertionError: assert False  (hasattr returns False)
```

- [ ] **Step 3: Add `import asyncio` to `wiki_manager.py`**

Open `backend/agent/wiki_manager.py`. The first line is `import os`. Add `import asyncio` immediately after it:

```python
import os
import asyncio
import datetime
import re
```

- [ ] **Step 4: Add `_write_lock` to `WikiManager.__init__`**

Find the `__init__` method. After `self.llm = self._init_llm()`, add:

```python
        self._write_lock = asyncio.Lock()
```

The full `__init__` block should look like:

```python
    def __init__(self, sources_dir="sources", wiki_dir="wiki"):
        self.sources_dir = sources_dir
        self.wiki_dir = wiki_dir
        self.llm = self._init_llm()
        self._write_lock = asyncio.Lock()

        # Ensure directories exist
        if not os.path.exists(self.sources_dir):
            os.makedirs(self.sources_dir, exist_ok=True)
        if not os.path.exists(self.wiki_dir):
            os.makedirs(self.wiki_dir, exist_ok=True)
```

- [ ] **Step 5: Restructure `ingest_source` into two phases**

Replace the entire `ingest_source` method (lines 85–125) with:

```python
    async def ingest_source(self, file_name: str):
        # Phase 1 — Read and LLM inference (runs concurrently across uploads)
        file_path = os.path.join(self.sources_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        parser = PydanticOutputParser(pydantic_object=IngestionResult)

        prompt = PromptTemplate(
            template="Extract key information from the following document.\n{format_instructions}\nDocument:\n{content}\n",
            input_variables=["content"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | self.llm | parser
        result = await chain.ainvoke({"content": content})

        # Phase 2 — File writes (serialized: one ingestion at a time)
        async with self._write_lock:
            # 1. Write Source Summary Page
            source_title = f"Summary_{file_name}"
            source_content = f"# Summary of {file_name}\n\n{result.source_summary}\n\n## Extracted Entities\n"
            for entity in result.entities:
                source_content += f"- [[{entity.name}]]\n"
            self._write_page(source_title, source_content)

            # 2. Update/Create Entity Pages
            for entity in result.entities:
                entity_path = self._get_page_path(entity.name)
                if os.path.exists(entity_path):
                    with open(entity_path, "a", encoding="utf-8") as f:
                        f.write(f"\n\n### Updated from {file_name}\n\n{entity.details}\n")
                else:
                    self._write_page(entity.name, f"# {entity.name}\n\n{entity.summary}\n\n## Details\n\n{entity.details}\n")

            # 3. Maintain wiki structure
            self.update_index()
            self._append_to_log("ingest", f"Processed {file_name}")

        return result
```

- [ ] **Step 6: Run all wiki_manager tests to confirm green**

```bash
python -m pytest backend/tests/test_wiki_manager.py -v
```
Expected: all tests pass. Verify these specifically:
- `test_wiki_manager_has_write_lock` — PASS
- `test_concurrent_ingestion_no_corruption` — PASS
- `test_wiki_manager_ingest_source_cycle` — PASS (existing test, must not regress)

- [ ] **Step 7: Run the full test suite to confirm nothing else broke**

```bash
python -m pytest backend/tests/ -v
```
Expected: all existing tests pass, plus the 2 new ones. No failures.

- [ ] **Step 8: Commit**

```bash
git add backend/agent/wiki_manager.py backend/tests/test_wiki_manager.py
git commit -m "$(cat <<'EOF'
fix(wiki): serialize file writes with asyncio.Lock to prevent race conditions

Multiple simultaneous uploads ran ingest_source concurrently, causing
update_index() to snapshot the wiki directory before other coroutines had
written their entity pages — risking stale or corrupted index.md.

Split ingest_source into two phases: LLM inference runs freely (parallel),
file writes acquire _write_lock (serialized). One lock per WikiManager
instance, scoped to the FastAPI process lifetime.
EOF
)"
```
