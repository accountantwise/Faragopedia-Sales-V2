# Agent Versioning

A built-in versioning system that creates a new immutable agent version on every update, enabling safe staged rollouts.

## Details

Every modification to an agent (system prompt, tools, model, skills) creates a new numbered version. Existing sessions continue running on their original version. New sessions default to the latest version unless explicitly pinned to a specific version number. If an update produces no actual changes, no new version is created. This enables progressive rollouts: deploy version 3 to a subset of sessions before switching all traffic.
