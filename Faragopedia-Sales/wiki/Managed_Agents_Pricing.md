# Managed Agents Pricing

A three-component pricing model covering token usage, active compute time, and web search operations.

## Details

Token costs follow standard API pricing: Sonnet 4.6 is $3 input / $15 output per million tokens; Opus 4.6 is $5 input / $25 output per million tokens; Haiku 4.5 is faster and cheaper for simple tasks. Active runtime is $0.08 per session-hour, counting only time the agent is actively working (idle time is free). Web searches cost $10 per 1,000 searches. No separate container hosting fees. Example: 10 minutes active time + 50K input / 10K output tokens on Sonnet 4.6 + 5 web searches ≈ $0.36 total.
