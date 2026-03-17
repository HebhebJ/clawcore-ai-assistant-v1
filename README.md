# ClawCore

ClawCore is a local-first, workspace-based AI assistant runtime inspired by OpenClaw.

## MVP included

- Workspace loader for `AGENT.md`, `SOUL.md`, `TOOLS.md`, `USER.md`, `BOOTSTRAP.md`
- Session persistence (`transcript.jsonl`, `state.json`, `summary.md`, `tool_calls.jsonl`)
- Context builder that layers workspace files + history + memory + tools + user input
- Structured reason/act loop with max-step safeguards
- Tool registry with safe built-in tools:
  - `list_files`
  - `read_file`
  - `get_datetime`
  - `search_web`
  - `read_url`
- FastAPI endpoint: `POST /chat`
- Provider factory with `kimi` (default) and `mock`

## Run

```bash
python -m pip install -e .
```

Create/edit `.env` in the project root (already included in this repo):

```bash
LLM_PROVIDER=kimi
KIMI_API_KEY=your_key_here
KIMI_MODEL=kimi-k2-0711-preview
KIMI_BASE_URL=https://api.moonshot.ai/v1
KIMI_TIMEOUT_SECONDS=30
KIMI_TEMPERATURE=1
KIMI_MAX_TOKENS=800
MEMORY_DISTILL_EVERY_TURNS=6
MEMORY_RETRIEVAL_MODE=hybrid
```

Start API:

```bash
uvicorn src.core.app:app --reload
```

Run CLI (no API server needed):

```bash
python -m src.cli.chat
```

Or after install:

```bash
clawcore-chat
```

One-shot message mode:

```bash
python -m src.cli.chat --message "List workspace files"
```

Call chat:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"workspace_id":"default-agent","session_id":"session-001","message":"List workspace files"}'
```

For local offline behavior, set this in `.env`:

```bash
LLM_PROVIDER=mock
```

## Errors

- Missing `KIMI_API_KEY`/`KIMI_MODEL` with `LLM_PROVIDER=kimi` returns config error.
- Upstream provider failures map to HTTP 502 from `/chat`.

## Memory behavior

- Per-turn memory classifier attempts to store durable facts.
- Session distillation runs every `MEMORY_DISTILL_EVERY_TURNS` user turns.
- CLI also triggers a final memory distill on `/exit` and before `/new`.
- Memory retrieval defaults to `hybrid` mode (vector + keyword), configurable via:
  - `MEMORY_RETRIEVAL_MODE=hybrid` (default)
  - `MEMORY_RETRIEVAL_MODE=vector`
  - `MEMORY_RETRIEVAL_MODE=keyword`
- Vector index is stored at `workspaces/<id>/memory/embeddings.jsonl`.

## Token usage

- Each response now includes token metrics:
  - per-turn `prompt_tokens` and `completion_tokens`
  - cumulative session totals `session_prompt_tokens_total` and `session_completion_tokens_total`
  - `context_tokens_estimate` and `context_chars`
- Kimi uses provider usage values when available.
- Mock provider uses a lightweight token estimate.

## Workspace tool policy (v1)

- Effective tools are resolved per request as:
  - global registered tools
  - + `workspaces/<id>/skills/enabled.json`
  - + `TOOLS.md` directives
- `skills/enabled.json` supports:
  - `enabled_tools: ["tool_a", ...]`
  - `disabled_tools: ["tool_x", ...]` (optional)
- `TOOLS.md` supports simple directives:
  - `allow: tool_a, tool_b`
  - `deny: tool_x, tool_y`
- Precedence:
  - workspace config is applied first
  - `allow` narrows toolset
  - `deny` applies last and always wins
- Unknown tool names are skipped with warnings.
- If `enabled.json` is missing, all globally registered tools remain available.

## Workspace skills (manifest-based)

- Activate skills in `workspaces/<id>/skills/enabled.json`:
  - `enabled_skills: ["research-assistant"]`
- Each skill lives in `workspaces/<id>/skills/<skill-name>/` and can include:
  - `skill.json` (manifest)
  - `SKILL.md` (instructions injected into context under `[Active Skills]`)
- `skill.json` supports optional tool overrides:
  - `enabled_tools`, `disabled_tools`, `allow_tools`, `deny_tools`
- Skill tool overrides are merged with workspace config and `TOOLS.md` policy.
- Example installed skill: `skills/web-research`.
