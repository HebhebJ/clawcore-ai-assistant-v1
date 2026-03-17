from datetime import datetime, timezone
import logging

from src.agents.loop import AgentLoop
from src.agents.workspace_loader import WorkspaceLoader
from src.context.builder import ContextBuilder
from src.core.config import LLMSettings, load_llm_settings, load_memory_distill_every_turns
from src.llm.factory import create_provider
from src.llm.token_counter import estimate_tokens
from src.memory.distiller import MemoryDistiller
from src.memory.retrieval import MemoryRetrieval
from src.memory.writer import MemoryWriter
from src.skills.loader import collect_skill_tool_overrides, load_active_skills, render_skill_instructions
from src.security.validators import PROMPT_EXFILTRATION_REFUSAL, is_prompt_exfiltration_attempt
from src.sessions.manager import SessionManager
from src.tools.executor import ToolExecutor
from src.tools.policy import (
    ToolPolicy,
    WorkspaceToolConfig,
    load_workspace_tool_config,
    merge_tool_policies,
    parse_tools_policy,
    resolve_effective_tools,
)
from src.tools.registry import default_registry

logger = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(self, settings: LLMSettings | None = None, provider=None) -> None:
        self.workspace_loader = WorkspaceLoader()
        self.session_manager = SessionManager()
        self.memory_retrieval = MemoryRetrieval()
        self.memory_writer = MemoryWriter()
        self.context_builder = ContextBuilder()
        self.settings = settings or load_llm_settings()
        self.memory_distiller = MemoryDistiller(self.session_manager, self.memory_writer, self.settings)
        self.memory_distill_every_turns = load_memory_distill_every_turns()
        self.provider = provider or create_provider(self.settings)
        self.tools = default_registry()
        self.tool_executor = ToolExecutor(self.tools)
        self.loop = AgentLoop()

    def handle_message(self, workspace_id: str, session_id: str, message: str) -> dict:
        workspace = self.workspace_loader.load(workspace_id)
        session = self.session_manager.load_or_create(workspace_id, session_id)
        session_totals = session.get("state", {}).get("token_totals", {"input": 0, "output": 0})
        memory_retrieval_mode = getattr(self.memory_retrieval, "mode", "hybrid")
        workspace_path = str(workspace.get("workspace_path", ""))
        workspace_config = load_workspace_tool_config(workspace_path)
        workspace_config = workspace_config or WorkspaceToolConfig()
        active_skills = load_active_skills(workspace_path, workspace_config.enabled_skills)
        skill_overrides = collect_skill_tool_overrides(active_skills)
        merged_workspace_config = WorkspaceToolConfig(
            enabled_tools=workspace_config.enabled_tools + skill_overrides["enabled_tools"],
            disabled_tools=workspace_config.disabled_tools + skill_overrides["disabled_tools"],
            enabled_skills=workspace_config.enabled_skills,
        )
        tools_policy = parse_tools_policy(workspace.get("TOOLS.md", ""))
        skill_policy = ToolPolicy(
            allow_tools=skill_overrides["allow_tools"],
            deny_tools=skill_overrides["deny_tools"],
        )
        merged_policy = merge_tool_policies(skill_policy, tools_policy)
        effective_tools = resolve_effective_tools(
            global_tools=self.tools,
            workspace_config=merged_workspace_config,
            policy=merged_policy,
        )
        logger.info("workspace=%s effective_tools=%s", workspace_id, list(effective_tools.keys()))
        skill_instructions = render_skill_instructions(active_skills)

        now = datetime.now(timezone.utc).isoformat()
        self.session_manager.append_transcript(
            workspace_id,
            session_id,
            {"role": "user", "content": message, "timestamp": now},
        )

        if is_prompt_exfiltration_attempt(message):
            result = {
                "answer": PROMPT_EXFILTRATION_REFUSAL,
                "steps": 0,
                "tool_calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "model_calls": 0,
                "context_chars": 0,
                "context_tokens_estimate": 0,
                "retrieved_memories_count": 0,
                "memory_retrieval_mode": memory_retrieval_mode,
                "session_prompt_tokens_total": int(session_totals.get("input", 0)),
                "session_completion_tokens_total": int(session_totals.get("output", 0)),
            }
            self.session_manager.append_transcript(
                workspace_id,
                session_id,
                {
                    "role": "assistant",
                    "content": result["answer"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            summary_info = self.session_manager.schedule_summary_update(
                workspace_id,
                session_id,
                result["answer"],
                user_message=message,
            )
            turn_count = self.session_manager.increment_turn_count(workspace_id, session_id)
            distill_info = None
            if turn_count % self.memory_distill_every_turns == 0:
                distill_info = self._run_memory_distill(workspace_id, session_id)
                if distill_info:
                    result["session_prompt_tokens_total"] = distill_info["session_prompt_tokens_total"]
                    result["session_completion_tokens_total"] = distill_info["session_completion_tokens_total"]
            result["memory_distill"] = distill_info
            result["summary_update"] = summary_info
            return result

        memories = self.memory_retrieval.retrieve(workspace_id, message)
        retrieved_memories_count = len(memories)
        context = self.context_builder.build(
            workspace=workspace,
            session=session,
            memories=memories,
            tools=effective_tools,
            user_message=message,
            skill_instructions=skill_instructions,
        )
        context_chars = len(context)
        context_tokens_estimate = estimate_tokens(context)

        if not effective_tools:
            result = {
                "answer": "No tools are enabled for this workspace right now. Update skills/enabled.json or TOOLS.md policy.",
                "steps": 0,
                "tool_calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "model_calls": 0,
                "context_chars": context_chars,
                "context_tokens_estimate": context_tokens_estimate,
                "retrieved_memories_count": retrieved_memories_count,
                "memory_retrieval_mode": memory_retrieval_mode,
                "session_prompt_tokens_total": int(session_totals.get("input", 0)),
                "session_completion_tokens_total": int(session_totals.get("output", 0)),
            }
            self.session_manager.append_transcript(
                workspace_id,
                session_id,
                {
                    "role": "assistant",
                    "content": result["answer"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            summary_info = self.session_manager.schedule_summary_update(
                workspace_id,
                session_id,
                result["answer"],
                user_message=message,
            )
            turn_count = self.session_manager.increment_turn_count(workspace_id, session_id)
            distill_info = None
            if turn_count % self.memory_distill_every_turns == 0:
                distill_info = self._run_memory_distill(workspace_id, session_id)
                if distill_info:
                    result["session_prompt_tokens_total"] = distill_info["session_prompt_tokens_total"]
                    result["session_completion_tokens_total"] = distill_info["session_completion_tokens_total"]
            result["memory_distill"] = distill_info
            result["summary_update"] = summary_info
            return result

        result = self.loop.run(
            provider=self.provider,
            context=context,
            tools=effective_tools,
            execute_tool=lambda name, tool_input: self._execute_tool(
                workspace_id, session_id, name, tool_input
            ),
        )
        prompt_tokens = int(result.get("prompt_tokens", 0))
        completion_tokens = int(result.get("completion_tokens", 0))
        totals = self.session_manager.add_token_usage(
            workspace_id=workspace_id,
            session_id=session_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        self.session_manager.append_transcript(
            workspace_id,
            session_id,
            {
                "role": "assistant",
                "content": result["answer"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        summary_info = self.session_manager.schedule_summary_update(
            workspace_id,
            session_id,
            result["answer"],
            user_message=message,
        )
        self.memory_writer.maybe_store(workspace_id, message, result["answer"])
        turn_count = self.session_manager.increment_turn_count(workspace_id, session_id)
        distill_info = None
        if turn_count % self.memory_distill_every_turns == 0:
            distill_info = self._run_memory_distill(workspace_id, session_id)
        result["context_chars"] = context_chars
        result["context_tokens_estimate"] = context_tokens_estimate
        result["retrieved_memories_count"] = retrieved_memories_count
        result["memory_retrieval_mode"] = memory_retrieval_mode
        if distill_info:
            result["session_prompt_tokens_total"] = distill_info["session_prompt_tokens_total"]
            result["session_completion_tokens_total"] = distill_info["session_completion_tokens_total"]
        else:
            result["session_prompt_tokens_total"] = int(totals.get("input", 0))
            result["session_completion_tokens_total"] = int(totals.get("output", 0))
        result["memory_distill"] = distill_info
        result["summary_update"] = summary_info

        return result

    def flush_memory(self, workspace_id: str, session_id: str) -> dict:
        info = self._run_memory_distill(workspace_id, session_id)
        return info or {"ran": False, "saved": 0, "prompt_tokens": 0, "completion_tokens": 0, "mode": "none"}

    def _execute_tool(self, workspace_id: str, session_id: str, name: str, tool_input: dict) -> str:
        output = self.tool_executor.execute(workspace_id, name, tool_input)
        self.session_manager.append_tool_call(
            workspace_id,
            session_id,
            {"tool_name": name, "input": tool_input, "output": output},
        )
        return output

    def _run_memory_distill(self, workspace_id: str, session_id: str) -> dict | None:
        info = self.memory_distiller.distill_session(workspace_id, session_id)
        if not info.get("ran"):
            return info
        totals = self.session_manager.add_token_usage(
            workspace_id=workspace_id,
            session_id=session_id,
            prompt_tokens=int(info.get("prompt_tokens", 0)),
            completion_tokens=int(info.get("completion_tokens", 0)),
        )
        info["session_prompt_tokens_total"] = int(totals.get("input", 0))
        info["session_completion_tokens_total"] = int(totals.get("output", 0))
        return info
