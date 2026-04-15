# Fast Mode

An optional speed optimization for Opus 4.6 that increases output generation speed.

## Details

Enabled by passing the model as an object with a 'speed' field set to 'fast' instead of passing the model ID as a string. Example: model={"id": "claude-opus-4-6", "speed": "fast"}. Useful for cost and latency optimization when using Opus for tasks that don't require maximum deliberation.
