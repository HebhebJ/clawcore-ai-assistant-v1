Absolutely — this is the right project.

You should build a **local-first AI assistant framework** inspired by OpenClaw, but simpler and cleaner, so you deeply understand:

* the **reason/act loop**
* **session context**
* **memory layers**
* **editable agent files** like `AGENT.md`, `TOOLS.md`, `USER.md`, `SOUL.md`
* **tool registration**
* **workspace-based agents**
* later: **multi-agent routing**

I’d define the project like this:

# Project name

**ClawCore**
A modular AI assistant runtime with editable workspace files, session memory, tool calling, and a controllable agent loop.

You can rename it later.

---

# 1. Project goal

Build an AI assistant system where each agent is a folder-based workspace with:

* editable identity/instruction files
* its own sessions
* its own memory
* its own tool access
* its own working directory

The assistant should:

* receive a user message
* load session context
* load agent files
* retrieve memory
* decide whether to answer or call tools
* execute tools safely
* update session + memory
* return final answer

So the final mental model is:

```text
User Message
  ↓
Agent Workspace Loader
  ↓
Context Builder
  ↓
LLM Reasoning Loop
  ↓
Tool Execution
  ↓
Memory Update
  ↓
Final Response
```

---

# 2. What this project is teaching you

This single project will make you practice almost everything important in agent engineering:

* prompt engineering
* context engineering
* tool schemas
* agent loops
* memory design
* session persistence
* workspace architecture
* guardrails
* observability
* extensibility

This is much better than building a random chatbot.

---

# 3. Core product concept

## One sentence

A **workspace-based AI assistant runtime** where behavior is controlled by editable markdown files and execution is powered by a reason-act-observe loop.

## Main philosophy

* **files define behavior**
* **code defines execution**
* **memory defines continuity**
* **tools define capability**

---

# 4. Main features for v1

## A. Workspace-based agents

Each agent lives in its own folder.

Example:

```text
/workspaces
  /default-agent
    AGENT.md
    SOUL.md
    TOOLS.md
    USER.md
    BOOTSTRAP.md
    /skills
    /memory
    /sessions
```

This makes the system very hackable.

## B. Editable markdown control files

You wanted the OpenClaw-like feeling — this is the key.

### `AGENT.md`

Core operating instructions.
What the agent does, priorities, task style, decision rules.

### `SOUL.md`

Tone, personality, communication style, behavioral boundaries.

### `TOOLS.md`

Tool usage policy, when to use tools, when not to, preferred sequencing.

### `USER.md`

Facts/preferences about the user.

### `BOOTSTRAP.md`

Loaded only at session start. Used for one-time setup behavior.

Optional later:

### `MEMORY_POLICY.md`

Rules for what gets stored in long-term memory.

---

# 5. Example meaning of each file

## AGENT.md

This is the agent’s job description.

Example sections:

* role
* mission
* core responsibilities
* workflow rules
* completion criteria
* escalation rules

Example:

```md
# Agent
You are a practical AI assistant focused on execution and structured help.

## Responsibilities
- Understand the user goal
- Use tools when needed
- Avoid hallucinating factual data
- Prefer concise actionable output

## Rules
- If a tool can verify a fact, use the tool
- Do not use tools for trivial reasoning
- Ask for clarification only if absolutely necessary
```

## SOUL.md

This is the vibe.

Example:

* calm
* technical
* direct
* not overly verbose
* strategic
* honest about uncertainty

## TOOLS.md

This file tells the model how to think about tools.

Example:

* Use `search_web` for current info
* Use `read_file` before editing files
* Never call a destructive tool without explicit permission
* Prefer one search before multiple searches

## USER.md

Could include:

* user likes technical explanations
* user is learning agent engineering
* user prefers practical builds
* user is interested in automation, ecommerce, and dev systems

## BOOTSTRAP.md

Loaded once at the start of a new session.
Example:

* greet in a certain style
* remind yourself of agent priorities
* initialize state plan

---

# 6. Main architecture

## Core modules

```text
/src
  /api
  /core
  /agents
  /tools
  /memory
  /sessions
  /context
  /llm
  /observability
  /security
```

### `/api`

REST API for chat, sessions, workspaces, tools.

### `/core`

Main orchestrator and app wiring.

### `/agents`

Agent runtime, loop engine, workspace loader.

### `/tools`

Tool registry, schemas, executors.

### `/memory`

Short-term, long-term, vector retrieval.

### `/sessions`

Session store and transcript persistence.

### `/context`

Prompt/context assembly pipeline.

### `/llm`

Provider abstraction for OpenAI/OpenRouter/Ollama/etc.

### `/observability`

Logs, traces, tool-call history, token usage.

### `/security`

Tool permissions, validation, confirmation gates.

---

# 7. The runtime flow

For each user message:

## Step 1 — Load workspace

Read:

* `AGENT.md`
* `SOUL.md`
* `TOOLS.md`
* `USER.md`
* `BOOTSTRAP.md` if first session turn

## Step 2 — Load session context

Load:

* recent conversation turns
* current session summary
* current working state

## Step 3 — Retrieve memory

Search long-term memory for relevant facts.

## Step 4 — Build prompt context

Assemble:

* system instructions from files
* available tools
* retrieved memory
* recent history
* current user message

## Step 5 — Run reasoning loop

Model decides:

* answer directly
* call tool
* continue reasoning
* finish

## Step 6 — Execute tools if requested

Validate inputs, run tool, capture output.

## Step 7 — Update state

Store:

* transcript
* tool calls
* memory candidates
* session summary

## Step 8 — Return response

---

# 8. The agent loop you should implement

Start with a clean loop.

```text
Initialize state
↓
Build context
↓
Call model
↓
If tool requested:
    validate
    execute
    append observation
    continue
Else if final answer:
    return output
Else:
    stop safely
```

Add protections:

* max steps
* max tool calls
* timeout
* invalid tool fallback

A good v1 limit:

* max reasoning steps: 6
* max tool calls: 4

---

# 9. Session system

You specifically mentioned session context, so design this carefully.

## Session responsibilities

* keep chat history
* keep rolling summary
* track active task state
* store tool traces

## Suggested storage

```text
/workspaces/default-agent/sessions/
  session-001/
    transcript.jsonl
    summary.md
    state.json
    tool_calls.jsonl
```

### `transcript.jsonl`

Full append-only event log.

### `summary.md`

Compressed session summary to avoid huge context.

### `state.json`

Current working state:

* goal
* current plan
* completed steps
* pending steps

### `tool_calls.jsonl`

For debugging and observability.

---

# 10. Memory system design

Implement 3 layers.

## A. Short-term memory

Recent conversation turns.
This lives in the current session.

## B. Session summary memory

A rolling summary of the session, refreshed every few turns.

## C. Long-term memory

Facts worth keeping across sessions.

Suggested structure:

```text
/workspaces/default-agent/memory/
  facts.jsonl
  notes.jsonl
  embeddings.db
```

For v1 you can skip vector DB at first and use simple keyword retrieval.
Then add embeddings later.

## What to store in long-term memory

Only useful reusable facts:

* user preferences
* project facts
* repeated goals
* important constraints

Do not store everything.

---

# 11. Memory write policy

Create a memory classifier step.

After each assistant turn, ask:

* Is there anything worth storing?
* Is it durable?
* Is it useful later?
* Is it user-specific or project-specific?

Possible memory categories:

* `user_preference`
* `project_fact`
* `workflow_rule`
* `open_task`
* `environment_fact`

This will make the assistant feel much smarter.

---

# 12. Tool system design

## Tool architecture

Each tool should have:

* name
* description
* input schema
* execution handler
* safety level

Example internal interface:

```text
Tool
- id
- name
- description
- input_schema
- handler
- category
- risk_level
- requires_confirmation
```

## Good v1 tools

Start simple.

### Safe tools

* `read_file`
* `write_file`
* `list_files`
* `search_files`
* `search_web`
* `fetch_url`
* `calculator`
* `get_datetime`

### Medium-risk tools

* `run_shell_command`
* `edit_file`
* `create_note`

### High-risk tools

* `delete_file`
* `send_email`
* `post_to_api`

In v1, maybe implement only safe + one medium-risk tool.

---

# 13. Tool policy layer

You wanted `TOOLS.md`, so use it meaningfully.

The final tool availability should come from:

```text
Global registered tools
+ Workspace-enabled tools
+ TOOLS.md usage rules
= Effective toolset
```

That’s powerful because:

* code decides what exists
* workspace decides what is enabled
* markdown decides how it should be used

---

# 14. Context builder design

This is one of the most important parts.

Your final prompt should not just be “one system prompt.”

It should be composed from layers:

```text
[System Base Instructions]
[AGENT.md]
[SOUL.md]
[TOOLS.md]
[USER.md]
[BOOTSTRAP.md if first turn]
[Retrieved Memories]
[Session Summary]
[Recent Conversation]
[Tool Descriptions]
[Current User Message]
```

This is exactly the kind of context engineering that makes agents feel advanced.

---

# 15. Prompt layers

I recommend this split:

## Base system prompt

Hardcoded in code.
Contains non-editable runtime rules:

* follow JSON tool-call format
* never invent tool results
* respect max-step loop
* obey tool safety constraints

## Workspace prompt files

Editable by you:

* AGENT
* SOUL
* TOOLS
* USER
* BOOTSTRAP

This split is important because you want:

* stable runtime behavior
* editable agent behavior

---

# 16. Model abstraction

Build an LLM provider layer from the start.

Example providers:

* OpenAI
* OpenRouter
* Anthropic
* Ollama
* Gemini later

Interface idea:

```text
generate(messages, tools, config) -> model response
```

This prevents vendor lock-in.

For your case, this matters because you like comparing models and costs.

---

# 17. Suggested tech stack

Since you’re technical and may want to grow this into a platform:

## Backend

* **Python**
* **FastAPI**

## Storage

* SQLite first
* then Postgres later

## Vector memory

* simple local JSON first
* then `pgvector` or `Chroma`

## LLM clients

* OpenAI-compatible SDK
* OpenRouter support
* Ollama support

## Frontend

* simple React/Next.js or even minimal HTML first
* or CLI first for speed

## Observability

* plain logs first
* then tracing dashboard later

My advice:
Start with **backend + CLI or simple chat UI**, not full fancy frontend.

---

# 18. Recommended folder structure

```text
clawcore/
  README.md
  pyproject.toml
  .env
  /src
    /api
      chat.py
      sessions.py
      workspaces.py
    /core
      app.py
      config.py
      logging.py
    /agents
      runtime.py
      loop.py
      workspace_loader.py
      state.py
    /context
      builder.py
      prompt_layers.py
      tool_prompt.py
    /llm
      base.py
      openai_provider.py
      openrouter_provider.py
      ollama_provider.py
    /tools
      registry.py
      executor.py
      schemas.py
      builtins/
        files.py
        web.py
        utils.py
    /memory
      store.py
      retrieval.py
      writer.py
      summarizer.py
    /sessions
      manager.py
      transcript.py
      summary.py
    /security
      validators.py
      confirmations.py
      permissions.py
    /observability
      traces.py
      metrics.py
  /workspaces
    /default-agent
      AGENT.md
      SOUL.md
      TOOLS.md
      USER.md
      BOOTSTRAP.md
      /skills
      /memory
      /sessions
```

---

# 19. API endpoints

A clean API could be:

## Chat

* `POST /chat`
* body: `workspace_id`, `session_id`, `message`

## Sessions

* `POST /sessions`
* `GET /sessions/{id}`
* `GET /sessions/{id}/transcript`

## Workspaces

* `GET /workspaces`
* `POST /workspaces`
* `GET /workspaces/{id}/files`
* `PUT /workspaces/{id}/files/{name}`

## Tools

* `GET /tools`
* `GET /workspaces/{id}/tools`

## Memory

* `GET /workspaces/{id}/memory`
* `POST /workspaces/{id}/memory/reindex`

This gives you a real platform feel.

---

# 20. Internal data models

## Workspace

```text
id
name
path
enabled_tools
created_at
```

## Session

```text
id
workspace_id
title
created_at
updated_at
status
```

## Message event

```text
id
session_id
role
content
timestamp
```

## Tool call event

```text
id
session_id
tool_name
input
output
success
timestamp
```

## Memory record

```text
id
workspace_id
type
content
tags
importance
created_at
```

---

# 21. Reasoning output format

Do not let the model return random free-form actions.
Use structured output.

Example:

```json
{
  "thought": "I should search the web for current info.",
  "action": "tool_call",
  "tool_name": "search_web",
  "tool_input": {
    "query": "latest OpenRouter pricing"
  }
}
```

Or final:

```json
{
  "thought": "I have enough information.",
  "action": "final_answer",
  "final_answer": "..."
}
```

Even if you later hide `thought`, the runtime should parse structured actions.

---

# 22. Guardrails

Build these from day one.

## Required

* max step limit
* tool whitelist
* tool input validation
* file path sandboxing
* output size limits
* retry limits

## Strongly recommended

* dangerous tool confirmation
* prompt injection warning for external text
* redact secrets in logs

---

# 23. Observability

This is what most beginners skip.

For every message, log:

* session id
* workspace id
* tokens in/out
* tool calls
* latency
* stop reason

You’ll thank yourself later.

Add a per-run trace like:

```text
run_id
step_1: model_decision
step_2: search_web called
step_3: tool result appended
step_4: final answer
```

That will make debugging much easier.

---

# 24. Development phases

## Phase 1 — MVP

Build:

* one workspace
* one session
* one model provider
* no vector DB yet
* 3–4 tools
* simple loop
* markdown files loaded
* transcript persistence

Goal: working single-agent assistant.

## Phase 2 — Better memory

Add:

* session summaries
* long-term memory store
* memory write policy
* memory retrieval

Goal: assistant remembers useful stuff.

## Phase 3 — Workspace editor

Add:

* API or UI to edit `AGENT.md`, `SOUL.md`, etc.
* reload agent behavior instantly

Goal: OpenClaw-like editability.

## Phase 4 — Better tools

Add:

* web tools
* file tools
* shell tools with safety
* tool categories and permissions

## Phase 5 — Multi-agent

Add:

* multiple workspaces
* router/orchestrator
* handoff between agents

---

# 25. Best first MVP use case

Don’t build a generic “do anything” assistant first.

Build one assistant optimized for:
**technical planning + file-based project help**

Why?
Because it matches your interests and makes the tools obvious:

* read/write files
* search web
* summarize docs
* manage project notes

This will also help you later build your bigger dev-agent ideas.

---

# 26. Example MVP behavior

User says:
“Help me plan an ecommerce automation agent.”

Assistant:

1. loads workspace files
2. loads session summary
3. retrieves relevant memory
4. decides to answer directly or search web
5. maybe writes `plan.md`
6. stores project facts in memory
7. continues next turn with continuity

That’s already a serious assistant.

---

# 27. What makes this project special

Many beginner projects are just:

* chat UI
* model call
* response

Your project is much better because it has:

* editable agent personality
* session continuity
* memory architecture
* tool runtime
* clear separation of behavior vs code

This is real agent engineering.

---

# 28. Definition you can use for the project

Here’s a polished project description you can give to Codex or put in `README.md`:

## Project description

Build a modular AI assistant runtime inspired by OpenClaw. The system should support workspace-based agents whose behavior is defined by editable markdown files such as `AGENT.md`, `SOUL.md`, `TOOLS.md`, `USER.md`, and `BOOTSTRAP.md`. Each workspace should maintain its own sessions, memory, and enabled tools. The runtime should implement a structured reason-act-observe loop with tool calling, session context loading, memory retrieval, and transcript persistence. The goal is to create a local-first assistant framework that is easy to customize, inspect, and extend into a multi-agent platform.

---

# 29. Functional requirements

## Must have

* workspace-based agent loading
* editable markdown instruction files
* session persistence
* structured reasoning loop
* tool registry and execution
* memory retrieval
* final response generation

## Should have

* session summaries
* long-term memory storage
* tool permissions
* logs and traces
* API endpoints for editing workspace files

## Nice to have

* vector search
* multi-agent routing
* UI dashboard
* plugin/skill install system

---

# 30. Non-functional requirements

* modular architecture
* provider-agnostic LLM layer
* safe tool execution
* local-first file storage
* easy debugging
* easy addition of new tools
* easy addition of new workspaces

---

# 31. The most important design rule

Keep this rule:

**editable files shape the mind, code shapes the machinery**

That’s the heart of the project.

---

# 32. What I recommend you build first, exactly

Build this order:

1. workspace loader
2. base prompt composer
3. simple chat endpoint
4. structured agent loop
5. tool registry with 3 tools
6. transcript persistence
7. session summary
8. long-term memory
9. workspace file editor
10. multi-agent support

That is the smoothest path.

---

If you want, next I’ll turn this into a **full implementation spec** with:

* exact milestones
* task breakdown
* file-by-file responsibilities
* starter prompts for `AGENT.md`, `SOUL.md`, and `TOOLS.md`
