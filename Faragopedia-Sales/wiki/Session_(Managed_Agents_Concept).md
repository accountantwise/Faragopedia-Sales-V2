# Session (Managed Agents Concept)

A running instance of an agent inside an environment where actual task execution occurs.

## Details

Creating a session provisions the container but does not start work — the session sits idle until a message is sent. Sessions can be pinned to specific agent versions. Session statuses include: idle (waiting for input), running (actively working), rescheduling (retrying after transient error), and terminated (unrecoverable error). Sessions support multi-turn conversations, and agents retain full context from previous turns. Sessions can be deleted after sending an interrupt event to stop active execution.
