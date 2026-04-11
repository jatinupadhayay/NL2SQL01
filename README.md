# NL2SQL Clinic Assistant

An AI-powered Natural Language to SQL system built with **Vanna 2.0** and **FastAPI**. Ask questions about clinic data in plain English and get SQL results, summaries, and charts.

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Backend language |
| Vanna | 2.0.x | AI Agent for NL2SQL |
| FastAPI | Latest | REST API framework |
| SQLite | Built-in | Database |
| Google Gemini | gemini-2.5-flash | LLM for SQL generation (default) |
| Groq | llama-3.3-70b-versatile | LLM fallback (optional) |
| Plotly | Latest | Chart generation |

## LLM Provider

**Primary: Google Gemini** (`gemini-2.5-flash` via AI Studio free tier)

Groq is available as a fallback by setting `LLM_PROVIDER=groq` in `.env`. The system uses Vanna 2.0's `GeminiLlmService` by default and `OpenAILlmService` (OpenAI-compatible) for Groq.

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/jatinupadhayay/NL2SQL01.git
cd NL2SQL01
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your-key-from-aistudio.google.com
```

Get a free Gemini key at: https://aistudio.google.com/apikey

### 5. Create the database and seed agent memory

```bash
python setup_database.py
python seed_memory.py
```

### 6. Start the API server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Or in one command:

```bash
pip install -r requirements.txt && python setup_database.py && python seed_memory.py && uvicorn main:app --port 8000
```

### 7. Open in browser

- **Web UI:** http://localhost:8000
- **Swagger Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

## API Documentation

### POST /chat

Ask a question in natural language. Returns SQL, results, and a chart.

**Request:**

```json
{
  "question": "Show me the top 5 patients by total spending"
}
```

**Response (200):**

```json
{
  "message": "Here are the top 5 patients by total spending...",
  "sql_query": "SELECT p.first_name, p.last_name, SUM(t.cost) ...",
  "columns": ["first_name", "last_name", "total_spending"],
  "rows": [{"first_name": "John", "last_name": "Smith", "total_spending": 4500}],
  "row_count": 5,
  "chart": { "data": [...], "layout": {...} },
  "chart_type": "bar"
}
```

**Error Responses:**

| Code | Meaning |
|---|---|
| 400 | Unsafe SQL detected (INSERT, DELETE, DROP, etc.) |
| 429 | Rate limit exceeded (30 requests/minute) |
| 500 | Database error or LLM failed to generate SQL |
| 502 | LLM service error (API key issue or network) |

### GET /health

```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 28
}
```

### GET /

Serves the web UI (`index.html`).

## Architecture Overview

```
User Question (English)
        |
        v
  FastAPI Backend (main.py)
        |
        v
  Vanna 2.0 Agent (vanna_setup.py)
  - GeminiLlmService (LLM)
  - DemoAgentMemory (28 pre-seeded Q&A pairs)
  - DDL schema injected via SystemPromptBuilder
        |
        v
  SQL Validation (SQL Guard)
  - SELECT only, no dangerous keywords
  - No system table access
        |
        v
  SQLite Execution (SqliteRunner)
        |
        v
  Results + Summary + Plotly Chart
```

## Key Design Decisions

- **DDL schema in system prompt:** The full database schema (table names, column types, FK relationships, enum values) is injected into the LLM's system prompt via `DefaultSystemPromptBuilder`. This eliminates hallucinated column/table names.
- **SQL Guard via monkey-patching:** The `ToolRegistry.transform_args` method is intercepted to validate all generated SQL before execution, without modifying Vanna's internals.
- **LRU cache (128 entries):** Identical questions return cached responses instantly, avoiding redundant LLM calls.
- **Rate limiting (30/min):** Prevents API abuse using `slowapi`.

## Database Schema

5 tables simulating a clinic management system:

- **patients** (200 rows) - demographics, city, registration date
- **doctors** (15 rows) - 5 specializations, 5 departments
- **appointments** (500 rows) - statuses: Scheduled, Completed, Cancelled, No-Show
- **treatments** (350 rows) - linked to completed appointments
- **invoices** (300 rows) - statuses: Paid, Pending, Overdue

## Project Structure

```
NL2SQL01/
  setup_database.py     # Creates clinic.db with schema + dummy data
  seed_memory.py        # Seeds 28 Q&A pairs into DemoAgentMemory
  vanna_setup.py        # Vanna 2.0 Agent initialization + DDL schema
  main.py               # FastAPI app with /chat, /health, SQL guard
  index.html            # Web UI frontend
  requirements.txt      # Python dependencies
  .env.example          # Environment variable template
  README.md             # This file
  RESULTS.md            # Test results for 20 questions
  clinic.db             # Generated SQLite database
```
