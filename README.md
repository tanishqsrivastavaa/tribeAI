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
session store <----> session + context builder <---- compacted session summary
                            |
                            v
                          model
                            |
                            +---- final response ----> user
                            |
                            +---- tool call -------> approval gate --> tool runner
                                                               |
                                                               v
                                                          tool result
                                                               |
                                                               +----> session store
```

- **Session store:** An append-only, durable record of messages and compaction summaries for each run.
- **Message/session model:** A typed representation of user, assistant, tool-call, tool-result, system, and summary messages.
- **Context builder:** Selects the system instructions, current task, relevant conversation history, summaries, and recent tool output that fit within the model's context budget.
- **Agent loop:** Sends the assembled context to the model, applies execution limits, executes approved tools, appends results to the session, and repeats until the model returns a final response or the run is stopped.
- **Approval gate:** Applies the tool approval policy before a capability is exercised.
- **Tool runner:** Validates a tool request, confines it to the workspace, runs it, captures its result, and gives that result back to the agent as data.

Keeping these concerns separate makes behavior easy to trace: the session explains what happened, the context builder explains what the model saw, and the tool runner explains what the agent was allowed to do.

## Messages and Sessions

Every session is an ordered stream of typed messages. Each message records its role, content, timestamp, and stable identifier. Tool-related messages also preserve the tool name, call identifier, arguments, result, exit status, and error information.

The session is persisted as append-only JSONL: one event per line. This makes a run easy to inspect, replay into a context builder, resume after interruption, and compact without overwriting its raw history. A compaction summary is also an event in the same session stream, with the range of messages it represents.

## Tool Contract

Each tool exposes a small, explicit contract:

- A stable `name` and human-readable `description` for the model.
- A JSON input schema that is validated before execution.
- An execution handler that receives validated arguments and the current workspace context.
- A structured result containing output, errors, metadata, and an execution status.

Tools do not receive unrestricted process state. Their workspace context supplies the configured workspace root and the policy needed to decide whether the request is permitted.

## The Agentic Loop

At its core, Tribe is designed around a straightforward tool-use loop:

1. Receive a user request and record it in the session.
2. Build a bounded context from instructions, the active request, relevant history, and prior summaries.
3. Ask the model for either a response or one or more tool calls.
4. If the model requests a tool, validate it, request approval when required, execute it, and append the result to the session.
5. Rebuild context and continue until the model produces a final answer.

This loop is intentionally visible and extensible. Model selection belongs around this loop, not inside opaque agent behavior.

### Execution Limits

Every run has explicit limits so a malformed response or a stuck task cannot consume unbounded time or authority:

- A maximum number of model/tool rounds.
- A timeout for each tool execution.
- A maximum number of consecutive tool failures.
- A cancellation path that stops future model and tool work cleanly.
- A terminal error explaining which limit stopped the run, with the completed session retained for inspection.

The loop must stop when any limit is reached. Limits are part of the run configuration and are recorded with the session.

## Context Compaction

Long sessions eventually exceed a model's context window. Tribe will compact older history when the estimated next prompt reaches 60% of the selected model's context limit, while retaining the most recent messages verbatim. The remaining 40% is reserved for tool output and the model's response.

A compaction pass should preserve:

- The user's goal and constraints.
- Decisions that have been made and their rationale.
- Important files, commands, outputs, and errors.
- Work completed, work remaining, and current blockers.
- Facts the agent must not rediscover or contradict.

The resulting summary replaces an older span of raw messages in the next context build. Recent interaction remains available in full, while the summary carries forward the information needed to continue the task. Raw session history remains on disk for inspection and future re-compaction.

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

## Workspace Boundary and Approvals

The configured workspace root is the capability boundary for file tools. `read`, `grep`, and `write` resolve every requested path against that root and reject paths that escape it, including traversal and symlink escapes. `bash` runs with the workspace as its working directory; it is not a substitute for unrestricted filesystem access.

Tool calls follow an explicit approval policy:

| Capability | Default policy |
| --- | --- |
| `read` and `grep` within the workspace | Allow automatically |
| `write` | Ask for approval before modifying files |
| `bash` | Ask for approval before execution |

Approval decisions are recorded in the session with the associated tool call. A future non-interactive mode can configure a stricter or pre-approved policy, but it must never silently expand the workspace boundary.

## CLI and Observability

The command-line interface is the primary interface to the harness:

```text
tribe chat
tribe run "inspect the project and run its tests"
tribe run --workspace ./my-project --model <model> "fix the failing test"
tribe resume <session-id>
```

The CLI will expose session identifiers, workspace and model selection, and a verbose mode for observing runs. Verbose output records model requests, estimated context usage, compaction events, approval decisions, tool inputs and outcomes, durations, and the limit that ended a run. The persisted session remains the complete audit trail; console output is a concise live view.

## Status

Tribe is at the scaffold stage. The current repository contains the Python entry point; the runtime, session persistence, context compaction, approval gate, CLI, observability, and tool implementations are the intended next layers.
