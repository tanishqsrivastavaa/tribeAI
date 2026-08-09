# Tribe

Tribe is a minimal, personal agent harness inspired by [Pi](https://github.com/earendil-works/pi). It is an experiment in building an agent runtime from small, understandable parts instead of a large framework.

The goal is not to ship another general-purpose assistant. The goal is to own the loop: decide which model to use, which tools it can call, what enters its context window, and how the session survives long-running work.

## Design Principles

- Keep the runtime small enough to understand end to end.
- Make the agent loop explicit rather than hiding it behind abstractions.
- Treat tools as a narrow, inspectable capability boundary.
- Preserve useful session state while keeping model context bounded.
- Prefer local-first workflows and plain text artifacts.

## Architecture

The harness is organized around a few deliberately simple pieces:

```text
user input
    |
    v
session + context builder <---- compacted session summary
    |
    v
model
    |
    +---- final response ----> user
    |
    +---- tool call -------> tool runner
                               |
                               v
                           tool result
                               |
                               +----> session + context builder
```

- **Session:** The durable record of user messages, assistant responses, tool calls, tool results, and compaction summaries.
- **Context builder:** Selects the system instructions, current task, relevant conversation history, summaries, and recent tool output that fit within the model's context budget.
- **Agent loop:** Sends the assembled context to the model, executes requested tools, appends results to the session, and repeats until the model returns a final response or the run is stopped.
- **Tool runner:** Validates a tool request, runs it in the workspace, captures its result, and gives that result back to the agent as data.

Keeping these concerns separate makes behavior easy to trace: the session explains what happened, the context builder explains what the model saw, and the tool runner explains what the agent was allowed to do.

## The Agentic Loop

At its core, Tribe is designed around a straightforward tool-use loop:

1. Receive a user request and record it in the session.
2. Build a bounded context from instructions, the active request, relevant history, and prior summaries.
3. Ask the model for either a response or one or more tool calls.
4. If the model requests a tool, execute it and append the result to the session.
5. Rebuild context and continue until the model produces a final answer.

This loop is intentionally visible and extensible. Policies such as maximum iterations, approval requirements, tool timeouts, and model selection belong around this loop, not inside opaque agent behavior.

## Context Compaction

Long sessions eventually exceed a model's context window. Tribe will handle this by compacting older history into a durable summary while retaining the most recent messages verbatim.

A compaction pass should preserve:

- The user's goal and constraints.
- Decisions that have been made and their rationale.
- Important files, commands, outputs, and errors.
- Work completed, work remaining, and current blockers.
- Facts the agent must not rediscover or contradict.

The resulting summary replaces an older span of raw messages in the next context build. Recent interaction remains available in full, while the summary carries forward the information needed to continue the task. The raw session history can still be retained on disk for inspection and future re-compaction.

Compaction is a state-management concern, not an afterthought: a good summary lets an agent resume accurately; a poor one silently changes the task.

## Basic Tools

The initial tool surface is intentionally small:

| Tool | Purpose |
| --- | --- |
| `read` | Read a file or directory so the agent can inspect the workspace. |
| `grep` | Search file contents for symbols, text, and patterns. |
| `write` | Create or update files through a controlled interface. |
| `bash` | Run shell commands for builds, tests, version control, and project tooling. |

Each tool should have clear input and output contracts, operate within the workspace, and return enough structured information for the agent to make its next decision. More specialized tools can be added later, but the basic file and shell capabilities are enough for a useful coding harness.

## Status

Tribe is at the scaffold stage. The current repository contains the Python entry point; the runtime, session persistence, context compaction, and tool implementations are the intended next layers.
