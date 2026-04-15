# Claude Managed Agents

Anthropic's hosted cloud agent infrastructure that allows developers to run AI agents via API without managing their own containers or tool execution layers.

## Details

Currently in public beta, Claude Managed Agents is described as 'Claude Code as a Service.' It provides access to the same tools that power Claude Code (Bash, file operations, web search, etc.) via API. The system is built around four core concepts: Agents (model configuration and identity), Environments (cloud containers), Sessions (running instances), and Events (communication protocol). It supports all Claude 4.5 and later models. Key limitations include no built-in scheduling, cron, or heartbeat functionality — it is reactive-only and triggered exclusively by API calls. Pricing includes standard token costs, $0.08 per active session-hour, and $10 per 1,000 web searches.
