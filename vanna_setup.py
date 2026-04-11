import os
import sqlite3

from dotenv import load_dotenv

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.core.system_prompt.default import DefaultSystemPromptBuilder
from vanna.integrations.google import GeminiLlmService
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


SCHEMA_CONTEXT = """
You are querying a SQLite clinic management database. Here is the exact schema:

CREATE TABLE patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,              -- may be NULL
    phone TEXT,              -- may be NULL
    date_of_birth DATE,
    gender TEXT,             -- values: 'M' or 'F'
    city TEXT,               -- values: Mumbai, Delhi, Bangalore, Hyderabad, Chennai, Kolkata, Pune, Ahmedabad, Jaipur, Lucknow
    registered_date DATE
);

CREATE TABLE doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    specialization TEXT,     -- values: Dermatology, Cardiology, Orthopedics, General, Pediatrics
    department TEXT,         -- values: Skin Care, Heart Center, Bone & Joint, Primary Care, Childrens Health
    phone TEXT
);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    doctor_id INTEGER REFERENCES doctors(id),
    appointment_date DATETIME,
    status TEXT,             -- values: Scheduled, Completed, Cancelled, No-Show
    notes TEXT               -- may be NULL
);

CREATE TABLE treatments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER REFERENCES appointments(id),
    treatment_name TEXT,     -- values: Consultation, Routine Checkup, X-Ray, Blood Test, Physical Therapy, Minor Surgery
    cost REAL,               -- range: 50 to 5000
    duration_minutes INTEGER
);

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    invoice_date DATE,
    total_amount REAL,
    paid_amount REAL,
    status TEXT              -- values: Paid, Pending, Overdue
);

IMPORTANT NOTES:
- Use patients.id (NOT patient_id) when referencing patients in WHERE/JOIN on the patients table.
- treatments does NOT have patient_id — join via: treatments.appointment_id -> appointments.id -> appointments.patient_id -> patients.id
- doctors.department is different from doctors.specialization.
- Gender values are single-letter: 'M' and 'F' (not 'male'/'female').
- Use strftime() for date operations in SQLite (e.g., strftime('%Y-%m', date_column)).
- Use date('now', '-N months') for relative date filtering.
"""


class DefaultUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(id="default-user", username="default-user", group_memberships=["user"])


llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()

if llm_provider == "groq":
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY is required in .env when LLM_PROVIDER=groq")
    llm_service = OpenAILlmService(
        api_key=groq_api_key,
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    )
else:
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY is required in .env")
    llm_service = GeminiLlmService(
        api_key=google_api_key,
        model="gemini-2.5-flash",
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
    system_prompt_builder=DefaultSystemPromptBuilder(base_prompt=SCHEMA_CONTEXT),
)