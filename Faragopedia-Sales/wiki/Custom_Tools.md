# Custom Tools

User-defined tools that enable the agent to request actions which are executed by the caller's own code.

## Details

Custom tools are defined in the agent configuration with a name, description, and JSON Schema for input parameters. When the agent invokes a custom tool, the caller receives an agent.custom_tool_use event, executes the action in their own code, and returns results via a user.custom_tool_result event. Example use case: a lookup_customer tool that queries an internal database when called by a support agent.
