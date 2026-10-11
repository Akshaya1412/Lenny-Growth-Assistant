# The Lenny Growth Assistant

A grounded internal assistant for product and growth teams that works from Lenny’s podcast and newsletter transcript set, with a local Ollama-first demo and a browser-based artifact viewer.

## Overview
The application provides a source-grounded chat experience for questions about product strategy, distribution, growth loops, and writing systems. It stores sessions in PostgreSQL, retrieves relevant transcript chunks, answers using those excerpts, and can generate reusable Markdown or HTML artifacts that render in-app.

## Prerequisites
- Python 3.10+ (Python 3.14 works with the pinned PostgreSQL driver)
- PostgreSQL 17 installed locally; Docker is optional
- Ollama installed locally for the mandatory demo model
- Optional: OpenAI, Anthropic, or Claude Agent SDK credentials if you want cloud-provider routing

## Quick start

### Windows local setup
1. Install Ollama on Windows if it is not already installed.
   ```powershell
   winget install --id Ollama.Ollama -e
   ```
   If `winget` is unavailable, install the official Windows release from the Ollama website and reopen PowerShell.
2. Start Ollama and download the required model:
   ```powershell
   ollama serve
   ollama pull llama3.2
   ```
3. Confirm the PostgreSQL 17 Windows service is running in PowerShell:
   ```powershell
   Get-Service postgresql-x64-17
   ```
   If PostgreSQL's `bin` folder is not on `PATH`, connect with its default install path:
   ```powershell
   & 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h 127.0.0.1 -U postgres -d postgres
   ```
   Enter the PostgreSQL administrator password at the terminal prompt. In `psql`, create the application role and database:
   ```sql
   CREATE ROLE lenny_growth_app LOGIN;
   \password lenny_growth_app
   CREATE DATABASE lenny_growth OWNER lenny_growth_app;
   \q
   ```
   `\password` prompts for the role password without putting it in SQL history. Use that password only in your local `.env`.
4. Open PowerShell in the project root and create a compatible virtual environment:
   ```powershell
   cd "C:\Users\akshaya\Downloads\Lenny Growth Assistant"
   py -3.14 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
   The official Claude Agent SDK requires Python 3.10 or newer. Use a compatible interpreter rather than the system Python 3.8.
5. Create `.env` from the example only if it does not already exist, so existing local settings are preserved:
   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```
   Edit the `DATABASE_URL` line in `.env` and replace `replace_me` with the password created above:
   ```env
   USE_SQLITE_FALLBACK=false
   DATABASE_URL=postgresql+psycopg2://lenny_growth_app:replace_me@127.0.0.1:5432/lenny_growth
   ```
   Keep `OLLAMA_BASE_URL=http://localhost:11434` and `OLLAMA_MODEL=llama3.2:latest` for the installed local model.
6. Start the app from the project root:
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
7. Open http://localhost:8000/static/index.html
8. Check service and provider status:
   ```powershell
   Invoke-RestMethod http://localhost:8000/api/v1/health
   Invoke-RestMethod http://localhost:8000/api/v1/config
   ```
   When Ollama is selected and unavailable, chat requests return a clear service error; they do not use a mock response.

### Optional: Docker Compose PostgreSQL
1. Ensure Docker Desktop or Docker Engine is installed and running.
2. Start the Postgres service:
   ```powershell
   docker compose up -d db
   ```
3. Set `.env` to use the container database, matching its locally configured role and password:
   ```env
   USE_SQLITE_FALLBACK=false
   DATABASE_URL=postgresql+psycopg2://replace_with_local_user:replace_with_local_password@127.0.0.1:5432/lenny_growth
   ```
4. Start the API:
   ```powershell
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
5. Open http://localhost:8000/static/index.html

### SQLite fallback
SQLite remains available for quick local demos and tests by setting `USE_SQLITE_FALLBACK=true`. PostgreSQL remains the recommended local persistent store.

## Configuration
The app reads environment variables from `.env`. The example file includes safe defaults and optional provider settings.

Required values:
- `MODEL_PROVIDER=ollama` by default
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3.2`

Optional values:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `CLAUDE_AGENT_API_KEY` for the official Claude Agent SDK path
- `DATABASE_URL`
- `USE_SQLITE_FALLBACK=true` for a lightweight demo without PostgreSQL

## Model behavior
- Default behavior: use Ollama locally.
- Fallback behavior: if Ollama is unavailable, the app returns a clear local setup error and does not silently claim a live model response.
- Cloud provider switching: change `MODEL_PROVIDER` to `openai`, `anthropic`, or `claude_agent_sdk` and provide the relevant API key.
- The official Agent SDK package is `claude-agent-sdk`, not `anthropic`.

## Security and artifact safety
Generated HTML is sanitized with `bleach` and rendered inside a sandboxed iframe. The sanitizer strips scripts and unsafe attributes while keeping common formatting tags like headings, lists, emphasis, and links.

## Troubleshooting
- If the app says the database is degraded, start Postgres or set `USE_SQLITE_FALLBACK=true` in `.env`.
- If Ollama is unreachable, run `ollama serve` and confirm `ollama list` shows the model.
- If retrieval returns no sources, the transcript set is empty or the question is outside the available material.
- If container startup fails, ensure Docker is running and ports 5432 and 8000 are free.

## Tests
Run from the project root using the activated virtual environment:
```bash
python -m pytest -q
```

## Manual test plan
1. Create a new session.
2. Ask: “What are the most important lessons for product-market fit?”
3. Confirm the answer references transcript files and a source name.
4. Ask a follow-up question with context preserved.
5. Click “Generate artifact” and confirm the viewer renders HTML beside the chat.
6. Change the provider dropdown and rerun the question.

## Project docs
- [PRD.md](PRD.md)
- [design.md](design.md)
- [architecture.md](architecture.md)
