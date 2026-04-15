# Events (Managed Agents Concept)

The communication protocol used to send messages to agents and receive streaming responses via Server-Sent Events (SSE).

## Details

Key event types include: user.message (send input to agent), user.interrupt (stop agent mid-execution), user.custom_tool_result (return custom tool execution results), user.tool_confirmation (approve or deny permission-gated tool calls), agent.message (agent text response), agent.tool_use (agent invoking a tool), agent.tool_result (result of tool execution), agent.custom_tool_use (agent requesting custom tool execution), and session.status_idle (agent finished). Responses stream in real time.
