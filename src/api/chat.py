from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents.runtime import AgentRuntime
from src.core.errors import ProviderUpstreamError, RuntimeConfigError

router = APIRouter()


@lru_cache(maxsize=1)
def get_runtime() -> AgentRuntime:
    return AgentRuntime()


class ChatRequest(BaseModel):
    workspace_id: str = Field(default="default-agent")
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    steps: int
    tool_calls: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    session_prompt_tokens_total: int = 0
    session_completion_tokens_total: int = 0
    context_chars: int = 0
    context_tokens_estimate: int = 0
    retrieved_memories_count: int = 0
    memory_retrieval_mode: str = "hybrid"
    summary_update: dict = Field(default_factory=dict)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        runtime = get_runtime()
        result = await runtime.handle_message(
            workspace_id=req.workspace_id,
            session_id=req.session_id,
            message=req.message,
        )
        return ChatResponse(
            session_id=req.session_id,
            answer=result["answer"],
            steps=result["steps"],
            tool_calls=result["tool_calls"],
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            session_prompt_tokens_total=result.get("session_prompt_tokens_total", 0),
            session_completion_tokens_total=result.get("session_completion_tokens_total", 0),
            context_chars=result.get("context_chars", 0),
            context_tokens_estimate=result.get("context_tokens_estimate", 0),
            retrieved_memories_count=result.get("retrieved_memories_count", 0),
            memory_retrieval_mode=result.get("memory_retrieval_mode", "hybrid"),
            summary_update=result.get("summary_update", {}),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ProviderUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
