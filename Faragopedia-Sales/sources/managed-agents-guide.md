# Claude Managed Agents: The Full Guide

**What it is, how it works, what it costs, and where it falls short compared to self-hosted alternatives.**

Last updated: April 8, 2026

---

## What Are Managed Agents?

Claude Managed Agents is Anthropic's hosted agent infrastructure, currently in public beta. Instead of building your own agent loop, container sandbox, and tool execution layer, you define what the agent should do and Anthropic runs it in a cloud container on their infrastructure.

Think of it as **"Claude Code as a Service"** -- the same tools (Bash, file ops, web search, etc.) that power Claude Code, but accessible via API. You call it, it works, it streams results back.

The pitch: go from zero to a working agent in minutes instead of days.

### The Core Concepts

Managed Agents is built around four things:

| Concept | What It Is |
|---------|-----------|
| **Agent** | Your agent's brain. The model, system prompt, tools, MCP servers, and skills. Created once, reused across sessions. |
| **Environment** | The container your agent runs in. Pre-installed packages, networking rules, file system. |
| **Session** | A running instance of your agent inside an environment. This is where the actual work happens. |
| **Events** | How you talk to the agent and how it talks back. You send messages, it streams responses. |

---

## The Full Lifecycle

Here's how you go from nothing to a running agent. Five steps.

### Step 1: Create an Agent

This is where you define the agent's identity -- which model it uses, what tools it has, and how it behaves.

```python
from anthropic import Anthropic

client = Anthropic()

agent = client.beta.agents.create(
    name="Coding Assistant",
    model="claude-sonnet-4-6",
    system="You are a helpful coding assistant. Write clean, well-documented code.",
    tools=[
        {"type": "agent_toolset_20260401"},
    ],
)

print(f"Agent ID: {agent.id}")  # agent_01HqR2k7vXb...
```

Key details:
- `agent_toolset_20260401` enables all built-in tools (Bash, file ops, web search, etc.)
- Agents are **versioned** -- every update creates a new version, so you can pin sessions to specific versions
- The Agent ID persists. Create it once, reference it forever.

#### Model Support

You're not locked into one model. **All Claude 4.5 and later models are supported:**

| Model | Model ID | Best For |
|-------|----------|----------|
| **Opus 4.6** | `claude-opus-4-6` | Complex reasoning, hard problems, highest quality |
| **Sonnet 4.6** | `claude-sonnet-4-6` | Best balance of speed and intelligence (default) |
| **Haiku 4.5** | `claude-haiku-4-5-20251001` | Fast, cheap, good for simple tasks |

You can also enable **fast mode** on Opus for faster output. Pass the model as an object instead of a string:

```python
agent = client.beta.agents.create(
    name="Fast Opus Agent",
    model={"id": "claude-opus-4-6", "speed": "fast"},
    system="You are a helpful assistant.",
    tools=[{"type": "agent_toolset_20260401"}],
)
```

This matters for cost optimization. Use Haiku for lightweight tasks (summarization, formatting), Sonnet for most work, and Opus for the hard stuff. You can create separate agents for each model and route tasks accordingly.

#### The `ant` CLI -- Build Agents From Your Terminal

You don't have to write Python to create managed agents. Anthropic ships a dedicated CLI called `ant` that lets you create and manage agents, environments, and sessions right from your terminal. Install it via Homebrew, Go, or curl:

```bash
# Homebrew
brew install anthropics/tap/ant

# Or Go
go install github.com/anthropics/anthropic-cli/cmd/ant@latest

# Or direct download (Linux/WSL)
curl -fsSL \
  "https://github.com/anthropics/anthropic-cli/releases/latest/download/ant_$(uname -s)_$(uname -m).tar.gz" \
  | tar -xz -C /usr/local/bin ant
```

Then create agents using YAML inline:

```bash
# Create an agent
ant beta:agents create \
  --name "Coding Assistant" \
  --model claude-sonnet-4-6 \
  --system "You are a helpful coding agent." \
  --tool '{type: agent_toolset_20260401}'

# Create an environment
ant beta:environments create \
  --name "python-dev" \
  --config '{type: cloud, networking: {type: unrestricted}}'

# Create a session
ant beta:sessions create \
  --agent "$AGENT_ID" \
  --environment "$ENVIRONMENT_ID"

# Send a message
ant beta:sessions:events send \
  --session-id "$SESSION_ID" \
  --event '{type: user.message, content: [{type: text, text: "Hello!"}]}'
```

You can also pass full YAML configs via heredoc for more complex setups:

```bash
ant beta:agents create <<'YAML'
name: Financial Analyst
model: claude-sonnet-4-6
system: You are a financial analysis agent.
skills:
  - type: anthropic
    skill_id: xlsx
  - type: custom
    skill_id: skill_abc123
    version: latest
YAML
```

This is useful if you're already living in Claude Code or your terminal and don't want to write a Python script just to set up an agent.

#### Disabling Specific Tools

You can also disable specific tools:

```python
agent = client.beta.agents.create(
    name="Read-Only Researcher",
    model="claude-sonnet-4-6",
    tools=[
        {
            "type": "agent_toolset_20260401",
            "configs": [
                {"name": "bash", "enabled": False},
                {"name": "write", "enabled": False},
                {"name": "edit", "enabled": False},
            ],
        },
    ],
)
```

### Step 2: Create an Environment

The environment is the cloud container where your agent runs. You configure what's installed and what network access it has.

```python
environment = client.beta.environments.create(
    name="data-analysis",
    config={
        "type": "cloud",
        "packages": {
            "pip": ["pandas", "numpy", "scikit-learn"],
            "npm": ["express"],
        },
        "networking": {"type": "unrestricted"},
    },
)

print(f"Environment ID: {environment.id}")
```

Supported package managers: `pip`, `npm`, `apt`, `cargo`, `gem`, `go`. The container also comes with common runtimes pre-installed (Python, Node.js, Go, etc.).

**Networking options:**
- `unrestricted` -- full outbound access (default)
- `limited` -- only allow specific hosts you whitelist

```python
# Locked-down environment for production
config = {
    "type": "cloud",
    "networking": {
        "type": "limited",
        "allowed_hosts": ["api.example.com"],
        "allow_mcp_servers": True,
        "allow_package_managers": True,
    },
}
```

Environments persist until you archive or delete them. Multiple sessions share the same environment config, but each session gets its own isolated container instance.

### Step 3: Start a Session

A session ties your agent and environment together and creates a running instance.

```python
session = client.beta.sessions.create(
    agent=agent.id,
    environment_id=environment.id,
    title="Data analysis task",
)

print(f"Session ID: {session.id}")
```

**Important:** Creating a session provisions the container but does NOT start work. The session sits in `idle` status until you send it a message.

You can optionally pin a session to a specific agent version:

```python
session = client.beta.sessions.create(
    agent={"type": "agent", "id": agent.id, "version": 2},
    environment_id=environment.id,
)
```

This is useful for staged rollouts -- test version 3 on a few sessions before switching everyone over.

### Step 4: Send Events and Stream Responses

This is how you actually talk to the agent. You send events, it streams back responses in real time via Server-Sent Events (SSE).

```python
# Open a stream, then send a message
with client.beta.sessions.events.stream(session.id) as stream:
    client.beta.sessions.events.send(
        session.id,
        events=[
            {
                "type": "user.message",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze the CSV file at /data/sales.csv and create a summary report.",
                    },
                ],
            },
        ],
    )

    for event in stream:
        match event.type:
            case "agent.message":
                for block in event.content:
                    print(block.text, end="")
            case "agent.tool_use":
                print(f"\n[Using tool: {event.name}]")
            case "session.status_idle":
                print("\n\nAgent finished.")
                break
```

The event flow looks like this:

```
You send: user.message ("Analyze sales.csv")
    |
Agent streams back:
    agent.message    -> "I'll analyze the CSV file..."
    agent.tool_use   -> [Using tool: read]
    agent.tool_result -> (file contents)
    agent.tool_use   -> [Using tool: bash] (runs Python analysis)
    agent.tool_result -> (script output)
    agent.message    -> "Here's what I found..."
    session.status_idle -> Done.
```

**Multi-turn conversations:** When the session goes `idle`, you can send another `user.message` to continue the conversation. The agent retains full context from previous turns.

**Interrupting:** Send a `user.interrupt` event to stop the agent mid-execution and redirect it.

**Session statuses:**
| Status | What's Happening |
|--------|-----------------|
| `idle` | Waiting for your input. Sessions start here. |
| `running` | Actively working on your task. |
| `rescheduling` | Hit a transient error, retrying automatically. |
| `terminated` | Unrecoverable error. Session is done. |

### Step 5: Memory (Research Preview)

By default, sessions are ephemeral -- when a session ends, everything the agent learned is gone. Memory stores change that.

Memory stores let agents carry learnings across sessions: user preferences, project conventions, past mistakes, domain knowledge.

```python
# Create a memory store
store = client.beta.memory_stores.create(
    name="User Preferences",
    description="Per-user preferences and project context.",
)

# Seed it with content
client.beta.memory_stores.memories.write(
    memory_store_id=store.id,
    path="/formatting_standards.md",
    content="All reports use GAAP formatting. Dates are ISO-8601.",
)

# Attach to a session
session = client.beta.sessions.create(
    agent=agent.id,
    environment_id=environment.id,
    resources=[
        {
            "type": "memory_store",
            "memory_store_id": store.id,
            "access": "read_write",
            "prompt": "Check before starting any task.",
        }
    ],
)
```

How it works:
- The agent **automatically** checks memory stores before starting a task
- The agent **automatically** writes durable learnings when done
- No additional prompting needed on your side
- Up to **8 memory stores** per session
- Individual memories capped at 100KB (~25K tokens)
- Every change creates an immutable version for auditing
- You can redact specific versions for compliance (PII removal, etc.)

Memory tools the agent gets automatically:

| Tool | What It Does |
|------|-------------|
| `memory_list` | List documents in a store |
| `memory_search` | Full-text search across documents |
| `memory_read` | Read a document's contents |
| `memory_write` | Create or overwrite a document |
| `memory_edit` | Modify an existing document |
| `memory_delete` | Remove a document |

**Note:** Memory is in Research Preview. You need to request access.

---

## How You Trigger It

This is the most important thing to understand: **Managed Agents are triggered only by API calls.**

There is no built-in cron. No heartbeat. No scheduled wake-ups. No "check on things every 30 minutes."

The flow is always:
1. Your code sends a `user.message` event to a session
2. The agent works
3. The agent goes idle
4. Nothing happens until your code sends another message

### Ways to trigger a Managed Agent

| Method | How It Works |
|--------|-------------|
| **Direct API call** | Your app calls the session events endpoint. Most common. |
| **Webhook handler** | Your server receives a webhook (GitHub push, Stripe payment, etc.), then sends a message to the agent. |
| **External cron** | Trigger.dev, GitHub Actions, or a Linux cron job calls the API on a schedule. |
| **User action** | User clicks a button in your app, your backend triggers the agent. |

### Connecting to External Services (MCP Servers)

You can connect MCP servers to give the agent access to external tools. Example with GitHub:

```python
agent = client.beta.agents.create(
    name="GitHub Assistant",
    model="claude-sonnet-4-6",
    mcp_servers=[
        {
            "type": "url",
            "name": "github",
            "url": "https://api.githubcopilot.com/mcp/",
        },
    ],
    tools=[
        {"type": "agent_toolset_20260401"},
        {"type": "mcp_toolset", "mcp_server_name": "github"},
    ],
)
```

Auth is handled through **vaults** -- you register OAuth credentials once, then reference the vault ID when creating a session:

```python
session = client.beta.sessions.create(
    agent=agent.id,
    environment_id=environment.id,
    vault_ids=[vault.id],
)
```

Can you hook it up to Telegram, Slack, etc.? **Yes, but indirectly.** You'd need:
1. Your own server listening for Telegram/Slack messages
2. That server forwards the message to a Managed Agent session via API
3. The agent responds, your server sends the response back to Telegram/Slack

Or you connect an MCP server for that platform (if one exists). But the agent itself doesn't sit on Telegram -- it's API-only.

### Custom Tools

You can define custom tools where the agent requests an action, your code executes it, and you send the result back:

```python
agent = client.beta.agents.create(
    name="Support Agent",
    model="claude-sonnet-4-6",
    tools=[
        {"type": "agent_toolset_20260401"},
        {
            "type": "custom",
            "name": "lookup_customer",
            "description": "Look up a customer by email address",
            "input_schema": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Customer email"},
                },
                "required": ["email"],
            },
        },
    ],
)
```

When the agent calls `lookup_customer`, you get an `agent.custom_tool_use` event. Your code runs the lookup, then sends back a `user.custom_tool_result` event with the data.

---

## What It Costs

Three cost components:

| Component | Price |
|-----------|-------|
| **Token usage** | Standard API pricing. Sonnet 4.6: $3 input / $15 output per MTok. Opus 4.6: $5 input / $25 output per MTok. |
| **Active runtime** | **$0.08 per session-hour.** Only counts time the agent is actively working. Idle time (waiting for your next message) is free. |
| **Web searches** | **$10 per 1,000 searches.** |

There are no separate container hosting fees. The runtime charge covers the infrastructure.

**Example cost estimate:** An agent session that runs for 10 minutes of active time, uses Sonnet 4.6, consumes 50K input tokens and 10K output tokens, and does 5 web searches:
- Tokens: ~$0.30
- Runtime: ~$0.013 (10 min = 0.167 hours x $0.08)
- Web searches: $0.05
- **Total: ~$0.36**

---

## Built-in Tools

When you enable `agent_toolset_20260401`, the agent gets:

| Tool | What It Does |
|------|-------------|
| **Bash** | Run shell commands in the container |
| **Read** | Read files from the container filesystem |
| **Write** | Write files to the container filesystem |
| **Edit** | String replacement in files |
| **Glob** | File pattern matching (find files) |
| **Grep** | Regex text search across files |
| **Web Fetch** | Fetch and read content from URLs |
| **Web Search** | Search the web |

Plus:
- **MCP servers** -- connect to external tool providers (GitHub, Slack, etc.)
- **Custom tools** -- define your own tools, your code handles execution

---

## Skills -- Giving Your Agent Expertise

Skills are reusable knowledge packs that turn a general-purpose agent into a specialist. They load on demand, so they only take up context window space when the agent actually needs them.

Two types:
- **Pre-built Anthropic skills** -- document handling (Excel, PowerPoint, Word, PDF)
- **Custom skills** -- your own domain-specific workflows and context, uploaded to your organization

```python
agent = client.beta.agents.create(
    name="Financial Analyst",
    model="claude-sonnet-4-6",
    system="You are a financial analysis agent.",
    skills=[
        {"type": "anthropic", "skill_id": "xlsx"},
        {"type": "custom", "skill_id": "skill_abc123", "version": "latest"},
    ],
)
```

Max 20 skills per session. Custom skills are versioned, so you can pin to a specific version or use `latest`.

---

## Permission Policies -- Controlling What the Agent Can Do

By default, all built-in tools run automatically (`always_allow`). But you can require human approval before specific tools execute.

Two modes:
- **`always_allow`** -- tool runs automatically, no confirmation needed (default for built-in tools)
- **`always_ask`** -- session pauses and waits for you to approve or deny (default for MCP tools)

Example: allow everything except bash commands, which need approval:

```python
agent = client.beta.agents.create(
    name="Careful Coder",
    model="claude-sonnet-4-6",
    tools=[
        {
            "type": "agent_toolset_20260401",
            "default_config": {
                "permission_policy": {"type": "always_allow"},
            },
            "configs": [
                {
                    "name": "bash",
                    "permission_policy": {"type": "always_ask"},
                },
            ],
        },
    ],
)
```

When the agent tries to run a bash command, the session pauses with `stop_reason: requires_action`. Your app receives the proposed command, shows it to the user, and sends back either `allow` or `deny`:

```python
client.beta.sessions.events.send(
    session.id,
    events=[
        {
            "type": "user.tool_confirmation",
            "tool_use_id": tool_event.id,
            "result": "deny",
            "deny_message": "Don't delete files in production.",
        },
    ],
)
```

This is useful for building user-facing products where you want guardrails. Let the agent read and write code freely, but require approval before it runs commands or hits external APIs.

---

## Practical Use Cases Where It Shines

### 1. Building AI into Your Product
You're building a SaaS app and want to give users an AI coding assistant. Managed Agents gives you the backend -- you handle the UI, Anthropic handles the agent infrastructure. Versioned agents let you roll out updates gradually.

### 2. One-Off Async Tasks
"Analyze this codebase and write a report." Fire the API call, stream results, done. No need to spin up infrastructure for a one-time job.

### 3. Teams Without DevOps
If your team doesn't have the bandwidth to manage containers, deploy agent infrastructure, and handle tool execution, Managed Agents removes all of that. Zero infra.

### 4. Prototyping Agent Workflows
Before committing to self-hosted infrastructure, test your agent idea with Managed Agents. The API is simple enough to prototype in an afternoon.

### 5. Enterprise Deployments
Limited networking (allowlist only), vault-based credential management, memory versioning with audit trails and redaction -- these are enterprise compliance features built in from the start.

---

## The Big Gap: No Scheduling / Always-On

This is where Managed Agents falls short for power users.

**What I wanted:** An agent that wakes up every 30 minutes, checks my GitHub PRs, scans my inbox, monitors a deployment, and surfaces anything that needs attention. A proactive agent with a heartbeat.

**What I got:** An agent that sits there doing nothing until I explicitly call it via API.

### The Missing Pieces

| Feature | Managed Agents | What Power Users Want |
|---------|---------------|-----------------------|
| Cron/scheduling | None | "Run this every 30 minutes" |
| Heartbeat | None | "Check if anything needs attention periodically" |
| Always-on | No (idle until triggered) | Agent that monitors continuously |
| Proactive alerts | None | "Notify me if X happens" |
| Event-driven triggers | None (API-only) | "When a PR is opened, review it automatically" |

To get any of these behaviors, you need to build the scheduling layer yourself:
- **Trigger.dev** cron job that calls the Managed Agents API every N minutes
- **GitHub Actions** scheduled workflow
- **Linux cron** running a script that sends `user.message` events
- **Your own webhook server** that forwards events to sessions

This is a significant gap. For anyone building proactive agents, Managed Agents is only the execution layer -- you still need an orchestration layer on top.

---

## Comparison: Managed Agents vs Agent SDK + Trigger.dev vs OpenClaw

### The Three Approaches

**Claude Managed Agents** -- Anthropic hosts and runs your agent. You call the API, it works, it stops.

**Agent SDK + Trigger.dev** -- You write the agent logic with Claude's Agent SDK (same tools as Claude Code), then deploy it on Trigger.dev for scheduled execution, retries, and observability. You own the code, Trigger.dev handles the runtime.

**OpenClaw** -- Open-source, self-hosted AI agent framework. Runs on your own server. Connects to WhatsApp, Telegram, Discord, Slack, and 20+ channels. BYOK (Bring Your Own Key) -- use Claude, GPT-4o, Gemini, whatever you want.

### Head-to-Head

| Category | Managed Agents | Agent SDK + Trigger.dev | OpenClaw |
|----------|---------------|------------------------|----------|
| **Infra setup** | Zero | Medium (Trigger.dev account + deploy) | High (15-20 hours DevOps) |
| **Scheduling** | None (API-triggered only) | Full cron + retries + observability | Heartbeat + cron (built-in) |
| **Always-on** | No | Yes | Yes |
| **Model lock-in** | Claude only | Claude only | BYOK (Claude, GPT-4o, Gemini, DeepSeek) |
| **Multi-channel** | API + MCP servers | Whatever you build | WhatsApp, Telegram, Discord, Slack, 20+ |
| **Memory** | Built-in memory stores (research preview) | Roll your own | Conversation history + HEARTBEAT.md |
| **Cost model** | Tokens + $0.08/session-hr + $10/1K searches | Tokens + Trigger.dev plan ($0-$50/mo) | Server hosting ($5-20/mo) + token costs |
| **Version control** | Built-in agent versioning | Git (your code) | Git (your config) |
| **Enterprise features** | Networking controls, vaults, audit trails | Whatever you build | Depends on your setup |
| **Best for** | API-driven products, beginners, enterprise | Power users with custom workflows | Multi-channel personal assistant |

### OpenClaw's Heartbeat -- What Managed Agents Is Missing

OpenClaw has a built-in **heartbeat** feature. The gateway wakes your agent every 30 minutes (configurable), and the agent reads a `HEARTBEAT.md` file to know what to check. You can configure active hours so it only runs during business hours in your timezone.

It also has **cron** -- full Unix-style scheduling with five-field expressions. `0 9 * * 1` means 9 AM every Monday.

The difference:
- **Heartbeat** = "check if anything needs attention" (periodic awareness)
- **Cron** = "do this specific thing at this specific time" (precise scheduling)

Managed Agents has neither. You'd need to build this on top.

### Trigger.dev -- The Power User's Scheduling Layer

If you're already using the Claude Agent SDK, Trigger.dev gives you:
- **Cron schedules** -- "every 5 minutes", "9:30 AM every other Monday", etc.
- **Durable execution** -- if a task fails, it retries automatically
- **Observability** -- real-time logs, performance metrics, run history
- **Webhooks** -- trigger agents from GitHub events, Stripe payments, etc.

You write the agent logic with the Agent SDK, deploy it to Trigger.dev, and it runs on schedule. The agent gets the same tools as Claude Code (read files, run commands, edit code, web search).

---

## Who Should Use What

**Just getting started with AI agents?**
Use **Managed Agents**. Zero infrastructure to manage. Great defaults. Clean API. You can have a working agent in 15 minutes.

**Building AI features into a product?**
Use **Managed Agents**. Versioned agents, memory stores, enterprise networking controls, vault-based auth. It's designed for this.

**Need scheduled / proactive agents?**
Use **Agent SDK + Trigger.dev**. Full cron scheduling, durable execution, automatic retries, observability. This is the always-on agent pattern.

**Want a personal AI assistant on WhatsApp/Telegram/Discord?**
Use **OpenClaw**. Multi-channel out of the box, heartbeat for proactive behavior, BYOK so you're not locked into one model provider.

**Already a Claude Code power user?**
You probably already have a better setup for your specific workflows. Managed Agents adds value if you need to give agent access to non-technical team members or build agents into a product where users interact via your app's UI.

---

## Bottom Line

Claude Managed Agents is a solid on-ramp for people building with agents for the first time. The API is clean, the infrastructure is fully managed, and memory stores are genuinely useful. If you've never touched Claude Code or built an agent from scratch, this is the easiest way to start.

But for power users? The lack of scheduling is a dealbreaker for proactive agent patterns. Managed Agents is **reactive-only** -- you call it, it works, it stops. The "always-on agent that checks on things for you" pattern requires external scheduling on top.

If Anthropic adds native cron/heartbeat support and event-driven triggers (webhooks that auto-trigger sessions), Managed Agents becomes a much stronger competitor to the self-hosted approach. Until then, it's the execution layer -- not the full orchestration layer that power users need.

**The hypothesis holds:** great for beginners and product builders, not enough for people who already have Claude Code + Trigger.dev or OpenClaw running.

---

## Agent Lifecycle Management

A few things worth knowing about how agents evolve over time:

**Versioning:** Every time you update an agent (change the system prompt, add a tool, swap the model), it creates a new version. Version 1, version 2, version 3. Existing sessions keep running on whatever version they started with. New sessions use the latest version unless you pin them.

**Update semantics:**
- Omitted fields are preserved (you only send what changed)
- Scalar fields (model, system, name) get replaced
- Array fields (tools, mcp_servers, skills) get fully replaced -- if you want to add a tool, send the full array
- Metadata is merged at the key level
- If your update changes nothing, no new version is created

**Archiving:** When you're done with an agent, archive it. It becomes read-only. Existing sessions keep running, but no new sessions can use it.

**Deleting sessions:** You can delete sessions to clean up. A running session can't be deleted -- send an interrupt first. Files, memory stores, environments, and agents are independent and aren't affected by session deletion.

---

## What's Coming (Research Preview)

Three features are in limited research preview. You need to request access.

**Outcomes:** Define success criteria for a task. The agent self-evaluates its work and iterates until it meets the criteria. Useful for tasks where "good enough" requires judgment, not just a binary pass/fail.

**Multi-agent orchestration:** One agent can invoke other agents via `callable_agents`. A coordinator agent delegates subtasks to specialist agents. This is the multi-agent swarm pattern, managed by Anthropic's infrastructure.

**Memory:** (Covered above.) Persistent memory stores that survive across sessions. Already the most fleshed-out of the three preview features.

---

## Quick Reference

### API Endpoints

| Action | Endpoint |
|--------|----------|
| Create agent | `POST /v1/agents` |
| Update agent | `PATCH /v1/agents/{id}` |
| Archive agent | `POST /v1/agents/{id}/archive` |
| Create environment | `POST /v1/environments` |
| Create session | `POST /v1/sessions` |
| Send events | `POST /v1/sessions/{id}/events` |
| Stream events | `GET /v1/sessions/{id}/stream` |
| Create memory store | `POST /v1/memory_stores` |
| Write memory | `POST /v1/memory_stores/{id}/memories` |

### Required Headers

All requests need:
```
x-api-key: YOUR_API_KEY
anthropic-version: 2023-06-01
anthropic-beta: managed-agents-2026-04-01
```

### SDK Support

Available in Python, TypeScript, Go, Java, C#, Ruby, and PHP. The SDK sets the beta header automatically.

### Rate Limits

| Operation | Limit |
|-----------|-------|
| Create endpoints | 60 requests/minute |
| Read endpoints | 600 requests/minute |

### Research Preview Features (Request Access)

- **Outcomes** -- define success criteria, agent self-evaluates and iterates
- **Multi-agent** -- orchestrate multiple agents working together
- **Memory** -- persistent memory stores across sessions
