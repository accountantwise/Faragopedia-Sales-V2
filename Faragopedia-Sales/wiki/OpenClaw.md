# OpenClaw

An open-source, self-hosted AI agent framework with built-in multi-channel support and native scheduling via heartbeat and cron.

## Details

OpenClaw runs on the user's own server and supports 20+ communication channels including WhatsApp, Telegram, Discord, and Slack out of the box. It features a BYOK (Bring Your Own Key) model supporting Claude, GPT-4o, Gemini, DeepSeek, and others. Key differentiating features include a heartbeat system (wakes agent every 30 minutes, configurable, respects business hours via timezone settings, reads a HEARTBEAT.md file for context) and full Unix-style cron scheduling (five-field expressions). Memory is handled via conversation history and a HEARTBEAT.md file. Infrastructure cost is approximately $5–$20/month for server hosting plus token costs. Setup requires 15–20 hours of DevOps work.
