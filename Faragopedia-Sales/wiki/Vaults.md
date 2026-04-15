# Vaults

A credential management system for storing OAuth tokens and API keys used by MCP servers and external integrations.

## Details

Vaults allow OAuth credentials to be registered once at the organization level and referenced by vault_id when creating sessions. This avoids embedding credentials in agent or session configurations directly and provides centralized credential management for enterprise deployments.
