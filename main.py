import logging
import re
import sqlite3
import time
import types
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import plotly.graph_objects as go
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from vanna.core.tool.models import ToolRejection
from vanna.core.user import RequestContext
from seed_memory import seed_memory_async
from vanna_setup import agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("nl2sql")

DB_PATH = Path(__file__).with_name("clinic.db")
BLOCKED_SQL = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "EXEC", "EXECUTE",
    "GRANT", "REVOKE", "SHUTDOWN",
)
BLOCKED_PATTERNS = (r"\bxp_", r"\bsp_", r"\bsqlite_", r"\bsqlite_master\b")
REQUEST_STATE: dict[str, dict[str, Any]] = {}

limiter = Limiter(key_func=get_remote_address)

_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_MAX = 128


def _cache_get(key: str) -> dict[str, Any] | None:
    return _CACHE.get(key)


def _cache_set(key: str, value: dict[str, Any]) -> None:
    if len(_CACHE) >= _CACHE_MAX:
        oldest = next(iter(_CACHE))
        _CACHE.pop(oldest, None)
    _CACHE[key] = value

class ChatRequest(BaseModel):
    question: str = Field(..., max_length=500)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be empty")
        return value


def validate_sql(sql: str) -> str | None:
    """Return an error string if SQL is unsafe, else None."""
    text = sql.strip()
    if not text:
        return "Invalid SQL generated."
    if ";" in text.rstrip(";"):
        return "Only a single SELECT query is allowed."
    upper = text.upper()
    if not (
        upper.startswith("SELECT")
        or (upper.startswith("WITH") and re.search(r"\bSELECT\b", upper))
    ):
        return "Only SELECT queries are allowed."
    if any(re.search(rf"\b{word}\b", upper) for word in BLOCKED_SQL):
        return "Unsafe SQL detected."
    lowered = text.lower()
    if any(re.search(pattern, lowered) for pattern in BLOCKED_PATTERNS):
        return "System tables are not allowed."
    return None


def install_sql_guard() -> None:
    registry = getattr(agent, "tool_registry", None)
    if not registry or getattr(registry, "_sql_guard_installed", False):
        return

    original_transform_args = registry.transform_args

    async def guarded_transform_args(self, tool, args, user, context):
        result = await original_transform_args(tool, args, user, context)
        if isinstance(result, ToolRejection):
            return result
        if getattr(tool, "name", "") != "run_sql":
            return result
        state = REQUEST_STATE.setdefault(context.conversation_id, {})
        sql = getattr(result, "sql", "")
        state["sql"] = sql
        log.info("[%s] SQL generated: %s", context.conversation_id[:8], sql[:120])
        error = validate_sql(sql)
        if error:
            log.warning("[%s] SQL rejected: %s", context.conversation_id[:8], error)
            state["invalid_sql"] = error
            return ToolRejection(reason=error)
        return result

    registry.transform_args = types.MethodType(guarded_transform_args, registry)

    tool = getattr(registry, "_tools", {}).get("run_sql")
    wrapped_tool = getattr(tool, "_wrapped_tool", tool)
    if wrapped_tool and not getattr(wrapped_tool, "_sql_guard_execute_installed", False):
        original_execute = wrapped_tool.execute

        async def guarded_execute(self, context, args):
            state = REQUEST_STATE.setdefault(context.conversation_id, {})
            state["sql"] = getattr(args, "sql", state.get("sql", ""))
            result = await original_execute(context, args)
            if result.success:
                log.info("[%s] SQL executed successfully", context.conversation_id[:8])
                state["db_error"] = None
            else:
                err = result.error or result.result_for_llm
                log.error("[%s] DB error: %s", context.conversation_id[:8], err)
                state["db_error"] = err
            return result

        wrapped_tool.execute = types.MethodType(guarded_execute, wrapped_tool)
        wrapped_tool._sql_guard_execute_installed = True

    registry._sql_guard_installed = True
    log.info("SQL guard installed on ToolRegistry")


def get_memory_count() -> int:
    memory = getattr(agent, "agent_memory", None) or getattr(agent, "memory", None)
    if memory is None:
        return 0
    count = 0
    for name in ("_memories", "_text_memories"):
        items = getattr(memory, name, None)
        if isinstance(items, list):
            count += len(items)
    return count


def check_database() -> str:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("SELECT COUNT(*) FROM patients").fetchone()
        return "connected"
    except Exception:
        return "disconnected"


def build_request_context(request: Request) -> RequestContext:
    return RequestContext(
        cookies=dict(request.cookies),
        headers=dict(request.headers),
        remote_addr=request.client.host if request.client else None,
        query_params=dict(request.query_params),
    )


def build_chart(columns: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows or not columns:
        return {}
    x_key = columns[0]
    y_key = columns[1] if len(columns) > 1 else columns[0]
    fig = go.Figure(
        data=[
            go.Bar(
                x=[row.get(x_key) for row in rows],
                y=[row.get(y_key) for row in rows],
            )
        ]
    )
    fig.update_layout(
        title="Query Results",
        xaxis_title=x_key,
        yaxis_title=y_key,
        template="plotly_dark",
    )
    return fig.to_plotly_json()


install_sql_guard()
app = FastAPI(
    title="NL2SQL Clinic API",
    description="Ask questions in plain English — get SQL results from a clinic database.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
async def startup() -> None:
    if getattr(app.state, "memory_seeded", False):
        return
    log.info("Seeding agent memory on startup …")
    await seed_memory_async()
    app.state.memory_seeded = True
    log.info("Startup complete — memory items: %d", get_memory_count())


@app.post("/chat")
@limiter.limit("30/minute")
async def chat(payload: ChatRequest, request: Request) -> dict[str, Any]:
    question = payload.question
    cache_key = question.lower().strip()

    cached = _cache_get(cache_key)
    if cached:
        log.info("Cache hit for question: %s", question[:60])
        return cached

    log.info("Processing question: %s", question[:80])
    t0 = time.perf_counter()

    conversation_id = uuid.uuid4().hex
    message = ""
    agent_error = ""
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count = 0

    try:
        async for component in agent.send_message(
            request_context=build_request_context(request),
            message=question,
            conversation_id=conversation_id,
        ):
            rich = getattr(component, "rich_component", None)
            simple = getattr(component, "simple_component", None)

            text = getattr(simple, "text", None)
            if text:
                message = text.strip()
                if message.startswith("Error:"):
                    agent_error = message

            if hasattr(rich, "rows") and hasattr(rich, "columns"):
                rows = list(getattr(rich, "rows", []) or [])
                columns = list(getattr(rich, "columns", []) or [])
                row_count = int(getattr(rich, "row_count", len(rows)) or len(rows))

    except Exception as exc:
        REQUEST_STATE.pop(conversation_id, None)
        log.exception("Unexpected error for question %r", question)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    state = REQUEST_STATE.pop(conversation_id, {})
    sql_query = state.get("sql", "")
    elapsed = time.perf_counter() - t0
    log.info("Question answered in %.2fs | sql=%s", elapsed, sql_query[:80])

    if state.get("invalid_sql"):
        raise HTTPException(status_code=400, detail=state["invalid_sql"])
    if state.get("db_error"):
        raise HTTPException(status_code=500, detail="Database error while executing the query.")
    if agent_error:
        raise HTTPException(
            status_code=502,
            detail="LLM service error. Check GROQ_API_KEY and network settings.",
        )
    if not sql_query:
        raise HTTPException(status_code=500, detail="LLM failed to generate SQL. Try rephrasing your question.")

    if row_count == 0:
        message = "No data found for this query."

    rows = rows[:100]
    chart = build_chart(columns, rows)

    response = {
        "message": message or f"Query returned {row_count} row(s).",
        "sql_query": sql_query,
        "columns": columns,
        "rows": jsonable_encoder(rows),
        "row_count": row_count,
        "chart": jsonable_encoder(chart),
        "chart_type": "bar",
    }

    _cache_set(cache_key, response)
    return response


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "database": check_database(),
        "agent_memory_items": get_memory_count(),
    }
