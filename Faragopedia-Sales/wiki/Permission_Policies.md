# Permission Policies

Configuration settings that control whether agent tools run automatically or require human approval before execution.

## Details

Two permission modes exist: 'always_allow' (tool runs automatically, default for built-in tools) and 'always_ask' (session pauses for human approval, default for MCP tools). When a tool requiring approval is called, the session pauses with stop_reason 'requires_action.' The calling application receives the proposed action, can present it to a user, and sends back either an 'allow' or 'deny' confirmation via a user.tool_confirmation event, optionally including a deny_message.
