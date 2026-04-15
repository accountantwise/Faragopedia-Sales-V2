# Memory Stores

A research preview feature enabling persistent knowledge storage that survives across agent sessions.

## Details

Memory stores allow agents to carry learnings across sessions, including user preferences, project conventions, past mistakes, and domain knowledge. Agents automatically check memory stores before starting tasks and write durable learnings when done. Up to 8 memory stores can be attached per session. Individual memories are capped at 100KB (~25K tokens). Every change creates an immutable version for auditing, and specific versions can be redacted for compliance (e.g., PII removal). Memory tools include: memory_list, memory_search, memory_read, memory_write, memory_edit, and memory_delete. Access can be set to read_write or read-only.
