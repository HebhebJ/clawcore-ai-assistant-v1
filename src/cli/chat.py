import argparse
from datetime import datetime, timezone

from src.agents.runtime import AgentRuntime
from src.core.errors import ProviderUpstreamError, RuntimeConfigError


def _default_session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"cli-{stamp}"


def _print_banner(workspace_id: str, session_id: str) -> None:
    print("ClawCore CLI")
    print(f"workspace={workspace_id} session={session_id}")
    print("Commands: /help, /new, /exit")


def _print_help() -> None:
    print("/help  Show available commands")
    print("/new   Start a new session id")
    print("/exit  Quit the CLI")


def _print_memory_distill(info: dict | None) -> None:
    if not info or not info.get("ran"):
        return
    print(
        "memory> "
        f"saved={int(info.get('saved', 0))} "
        f"mode={info.get('mode', 'unknown')} "
        f"in_tokens={int(info.get('prompt_tokens', 0))} "
        f"out_tokens={int(info.get('completion_tokens', 0))}"
    )


def _print_summary_update(info: dict | None) -> None:
    if not info:
        return
    if info.get("background"):
        print(
            "summary> "
            f"queued=True provider={info.get('provider_configured', 'unknown')} "
            f"token_cap={int(info.get('token_cap', 0))}"
        )
        return
    fallback = str(info.get("fallback_reason", "")).strip()
    fallback_part = f" fallback={fallback}" if fallback else ""
    print(
        "summary> "
        f"provider={info.get('provider_used', 'unknown')} "
        f"compacted={bool(info.get('compacted', False))} "
        f"tokens={int(info.get('tokens_after', 0))}/{int(info.get('token_cap', 0))}"
        f"{fallback_part}"
    )


def _run_one_shot(runtime: AgentRuntime, workspace_id: str, session_id: str, message: str) -> int:
    result = runtime.handle_message(workspace_id=workspace_id, session_id=session_id, message=message)
    print(result["answer"])
    print(
        "meta> "
        f"steps={result['steps']} tool_calls={result['tool_calls']} "
        f"in_tokens={result.get('prompt_tokens', 0)} out_tokens={result.get('completion_tokens', 0)} "
        f"session_in_total={result.get('session_prompt_tokens_total', 0)} "
        f"session_out_total={result.get('session_completion_tokens_total', 0)} "
        f"context_tokens_est={result.get('context_tokens_estimate', 0)} "
        f"memory_mode={result.get('memory_retrieval_mode', 'unknown')} "
        f"memory_hits={result.get('retrieved_memories_count', 0)}"
    )
    _print_summary_update(result.get("summary_update"))
    _print_memory_distill(result.get("memory_distill"))
    return 0


def _run_interactive(runtime: AgentRuntime, workspace_id: str, session_id: str) -> int:
    _print_banner(workspace_id, session_id)

    active_session_id = session_id
    while True:
        try:
            raw = input("you> ").strip()
        except EOFError:
            _print_memory_distill(runtime.flush_memory(workspace_id=workspace_id, session_id=active_session_id))
            print("\nExiting.")
            return 0
        except KeyboardInterrupt:
            _print_memory_distill(runtime.flush_memory(workspace_id=workspace_id, session_id=active_session_id))
            print("\nExiting.")
            return 0

        if not raw:
            continue
        if raw == "/exit":
            _print_memory_distill(runtime.flush_memory(workspace_id=workspace_id, session_id=active_session_id))
            print("Exiting.")
            return 0
        if raw == "/help":
            _print_help()
            continue
        if raw == "/new":
            _print_memory_distill(runtime.flush_memory(workspace_id=workspace_id, session_id=active_session_id))
            active_session_id = _default_session_id()
            print(f"Started new session: {active_session_id}")
            continue

        try:
            result = runtime.handle_message(
                workspace_id=workspace_id,
                session_id=active_session_id,
                message=raw,
            )
            print(f"assistant> {result['answer']}")
            print(
                "meta> "
                f"steps={result['steps']} tool_calls={result['tool_calls']} "
                f"in_tokens={result.get('prompt_tokens', 0)} out_tokens={result.get('completion_tokens', 0)} "
                f"session_in_total={result.get('session_prompt_tokens_total', 0)} "
                f"session_out_total={result.get('session_completion_tokens_total', 0)} "
                f"context_tokens_est={result.get('context_tokens_estimate', 0)} "
                f"memory_mode={result.get('memory_retrieval_mode', 'unknown')} "
                f"memory_hits={result.get('retrieved_memories_count', 0)}"
            )
            _print_summary_update(result.get("summary_update"))
            _print_memory_distill(result.get("memory_distill"))
        except ValueError as exc:
            print(f"Input error: {exc}")
        except RuntimeError as exc:
            print(f"Runtime error: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ClawCore interactive CLI")
    parser.add_argument("--workspace-id", default="default-agent", help="Workspace id")
    parser.add_argument("--session-id", default=None, help="Session id (default: auto-generated)")
    parser.add_argument("--message", default=None, help="Run one-shot message and exit")
    args = parser.parse_args()

    session_id = args.session_id or _default_session_id()

    try:
        runtime = AgentRuntime()
        if args.message:
            return _run_one_shot(runtime, args.workspace_id, session_id, args.message)
        return _run_interactive(runtime, args.workspace_id, session_id)
    except RuntimeConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    except ProviderUpstreamError as exc:
        print(f"Provider error: {exc}")
        return 3
    except FileNotFoundError as exc:
        print(f"Workspace error: {exc}")
        return 4
    except ValueError as exc:
        print(f"Input error: {exc}")
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
