import os

from dotenv import load_dotenv

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.integrations.google import GeminiLlmService
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.sqlite import SqliteRunner
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
)

load_dotenv()


class DefaultUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(id="default-user", username="default-user", group_memberships=["user"])


llm_service = GeminiLlmService(api_key=os.getenv("GOOGLE_API_KEY"))
sqlite_runner = SqliteRunner(database_path="clinic.db")
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
