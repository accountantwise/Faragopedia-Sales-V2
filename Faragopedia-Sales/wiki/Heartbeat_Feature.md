# Heartbeat Feature

A proactive scheduling mechanism in OpenClaw that periodically wakes an agent to check for anything requiring attention.

## Details

OpenClaw's heartbeat wakes the agent every 30 minutes by default (configurable). The agent reads a HEARTBEAT.md file to know what to check. Active hours can be configured so the agent only runs during business hours in a specified timezone. This is distinguished from cron (precise scheduling) in that heartbeat represents periodic awareness — 'check if anything needs attention' — rather than executing a specific task at a specific time. Managed Agents has no equivalent feature.
