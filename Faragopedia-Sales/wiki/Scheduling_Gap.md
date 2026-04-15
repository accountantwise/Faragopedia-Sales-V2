# Scheduling Gap

The primary limitation of Managed Agents: no built-in cron, heartbeat, or event-driven triggers for proactive agent behavior.

## Details

Managed Agents is reactive-only — it executes only when explicitly triggered by an API call. There is no native cron scheduling, heartbeat, or webhook-to-session trigger. Proactive patterns (monitor PRs, check inbox, watch deployments) require an external scheduling layer such as Trigger.dev cron jobs, GitHub Actions scheduled workflows, Linux cron scripts, or custom webhook servers that forward events to sessions. The author identifies this as a dealbreaker for power users building always-on or proactive agents.
