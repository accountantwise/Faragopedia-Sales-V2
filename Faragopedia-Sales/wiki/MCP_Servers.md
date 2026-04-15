# MCP Servers

External tool providers that can be connected to agents to extend their capabilities beyond built-in tools.

## Details

MCP (Model Context Protocol) servers are connected by specifying a URL and name in the agent configuration. Authentication is managed through vaults — OAuth credentials are registered once and referenced via vault IDs when creating sessions. MCP tools default to 'always_ask' permission policy. Examples include GitHub integration via api.githubcopilot.com/mcp/. MCP servers enable indirect integration with platforms like Telegram and Slack if MCP servers exist for those platforms.
