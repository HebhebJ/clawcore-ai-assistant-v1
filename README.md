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
KIMI_TIMEOUT_SECONDS=60
KIMI_TEMPERATURE=1
KIMI_MAX_TOKENS=800
MEMORY_DISTILL_EVERY_TURNS=6
MEMORY_RETRIEVAL_MODE=hybrid
SUMMARY_UPDATER_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_SUMMARY_MODEL=gpt-oss:20b
SUMMARY_TOKEN_CAP=1000
SUMMARY_DELTA_MAX_LINES=3
SUMMARY_COMPACT_TARGET_TOKENS=350
SUMMARY_TIMEOUT_SECONDS=30
SUMMARY_TEMPERATURE=0.1
SUMMARY_OLLAMA_MAX_FAILURES=3
SUMMARY_OLLAMA_COOLDOWN_SECONDS=60
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_WORKSPACE_ID=default-agent
TELEGRAM_TIMEOUT_SECONDS=20
TELEGRAM_AUTO_SETUP=false
TELEGRAM_AUTO_NGROK=false
TELEGRAM_PUBLIC_BASE_URL=
TELEGRAM_LOCAL_PORT=8000
TELEGRAM_STARTUP_TIMEOUT_SECONDS=20
NGROK_PATH=ngrok
NGROK_AUTHTOKEN=
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

Telegram webhook:

- Endpoint: `POST /webhook/telegram`
- Session mapping:
  - Default first session: `tg-<chat_id>`
  - `/new` rotates to a fresh session id: `tg-<chat_id>-<utc-stamp>`
  - `/exit` closes current session; next message starts fresh
- Telegram chat commands:
  - `/new` flush memory for current session and start a new one
  - `/exit` flush memory and close current session
  - `/session` show current active session id
  - `/help` list Telegram commands
- If `TELEGRAM_WEBHOOK_SECRET` is set, requests must include header `X-Telegram-Bot-Api-Secret-Token`.
- Optional startup auto-setup:
  - `TELEGRAM_AUTO_SETUP=true` enables webhook auto registration at backend startup.
  - Use `TELEGRAM_PUBLIC_BASE_URL=https://...` if you already have a public URL.
  - Or set `TELEGRAM_AUTO_NGROK=true` (+ `NGROK_AUTHTOKEN`) to auto-start ngrok and register webhook.

Set Telegram webhook:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -d "url=https://<your-domain>/webhook/telegram" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

Or use helper script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_telegram_webhook.ps1 -PublicBaseUrl "https://<your-domain>"
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
- You can force memory capture with explicit phrasing such as:
  - `save to your memory: <fact>`
  - `memorize that <fact>`
  - `note this: <fact>`
- Session distillation runs every `MEMORY_DISTILL_EVERY_TURNS` user turns.
- CLI also triggers a final memory distill on `/exit` and before `/new`.
- Memory retrieval defaults to `hybrid` mode (vector + keyword), configurable via:
  - `MEMORY_RETRIEVAL_MODE=hybrid` (default)
  - `MEMORY_RETRIEVAL_MODE=vector`
  - `MEMORY_RETRIEVAL_MODE=keyword`
- Vector index is stored at `workspaces/<id>/memory/embeddings.jsonl`.
- Session summary appends a max `SUMMARY_DELTA_MAX_LINES` turn delta and auto-compacts when it exceeds `SUMMARY_TOKEN_CAP`.
- Summary updater can use local Ollama (`SUMMARY_UPDATER_PROVIDER=ollama`) with automatic heuristic fallback.
- Ollama summary fallback uses a failure threshold + cooldown (defaults: `SUMMARY_OLLAMA_MAX_FAILURES=3`, `SUMMARY_OLLAMA_COOLDOWN_SECONDS=60`) instead of one-time permanent disable.
- Summary updates are queued in the background (non-blocking for chat responses).
- CLI prints summary queue status as `summary> queued=True provider=... token_cap=...`.

## Token usage

- Each response now includes token metrics:
  - per-turn `prompt_tokens` and `completion_tokens`
  - cumulative session totals `session_prompt_tokens_total` and `session_completion_tokens_total`
  - `context_tokens_estimate` and `context_chars`
- Kimi uses provider usage values when available.
- Mock provider uses a lightweight token estimate.
- If the model returns an unsupported action format, the loop now retries once with a repair hint before stopping safely.

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
