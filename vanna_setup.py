import os
import sqlite3

from dotenv import load_dotenv

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.integrations.openai import OpenAILlmService
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.sqlite import SqliteRunner
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
)

load_dotenv()

for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "GIT_HTTP_PROXY", "GIT_HTTPS_PROXY"):
    if os.getenv(key) == "http://127.0.0.1:9":
        os.environ.pop(key, None)


class DefaultUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(id="default-user", username="default-user", group_memberships=["user"])


groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY is required in .env")

llm_service = OpenAILlmService(
    api_key=groq_api_key,
    base_url="https://api.groq.com/openai/v1",
    model="llama-3.3-70b-versatile",
)
sqlite_runner = SqliteRunner(database_path="clinic.db")


def warmup_schema() -> None:
    try:
        with sqlite3.connect("clinic.db") as conn:
            for table in ("patients", "doctors", "appointments", "treatments", "invoices"):
                conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchall()
    except sqlite3.Error:
        pass


warmup_schema()

agent_memory = DemoAgentMemory()
tool_registry = ToolRegistry()

tool_registry.register_local_tool(RunSqlTool(sql_runner=sqlite_runner), access_groups=[])
tool_registry.register_local_tool(VisualizeDataTool(), access_groups=[])
tool_registry.register_local_tool(SaveQuestionToolArgsTool(), access_groups=[])
tool_registry.register_local_tool(SearchSavedCorrectToolUsesTool(), access_groups=[])

agent = Agent(
    llm_service=llm_service,
    tool_registry=tool_registry,
    user_resolver=DefaultUserResolver(),
    agent_memory=agent_memory,
    config=AgentConfig(),
)
