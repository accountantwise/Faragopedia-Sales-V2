# Environment (Managed Agents Concept)

The cloud container configuration defining pre-installed packages, networking rules, and the filesystem for agent execution.

## Details

Environments support package managers including pip, npm, apt, cargo, gem, and go. Common runtimes (Python, Node.js, Go, etc.) are pre-installed. Networking can be set to 'unrestricted' (full outbound access) or 'limited' (allowlist of specific hosts). Multiple sessions share the same environment configuration but each session gets its own isolated container instance. Environments persist until archived or deleted.
