# Agent (Managed Agents Concept)

The configuration object defining an agent's identity, including its model, system prompt, tools, MCP servers, and skills.

## Details

Agents are created once and reused across sessions. Every update to an agent creates a new version, enabling version pinning for staged rollouts. The Agent ID persists indefinitely. Agents are configured with tools (including the agent_toolset_20260401 for all built-in tools), MCP servers, skills, and permission policies. Individual tools can be enabled or disabled. Agents can be archived to become read-only. Array fields (tools, mcp_servers, skills) are fully replaced on update, while scalar fields are replaced and metadata is merged.
