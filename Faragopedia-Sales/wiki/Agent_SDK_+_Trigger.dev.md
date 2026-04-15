# Agent SDK + Trigger.dev

An alternative architecture combining Anthropic's Agent SDK with Trigger.dev's job scheduling platform for always-on, scheduled agent execution.

## Details

In this pattern, developers write agent logic using Claude's Agent SDK (same tools as Claude Code), then deploy to Trigger.dev for execution. Trigger.dev provides full cron scheduling, durable execution with automatic retries on failure, real-time observability (logs, metrics, run history), and webhook-triggered execution. This approach supports always-on agent patterns that Managed Agents cannot provide natively. Cost model is tokens plus Trigger.dev plan ($0–$50/month). Recommended for power users with custom workflows who need proactive or scheduled agent behavior.
