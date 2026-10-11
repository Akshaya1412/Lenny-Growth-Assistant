# Architecture

## 1. System overview
The application is a FastAPI application with a lightweight static frontend. All runtime logic is server-side, which keeps the evaluator experience simple and makes it easier to reason about retrieval, provider routing, and security.

## 2. Database schema
The app stores sessions and messages in PostgreSQL by default, with a SQLite fallback for demo environments when Postgres is unavailable. The schema is intentionally small:

- chat_sessions
  - id
  - user_name
  - title
  - created_at
  - updated_at
- chat_messages
  - id
  - session_id
  - role
  - content
  - citations
  - created_at
  - artifact

## 3. API endpoints
- GET /api/v1/health
- GET /api/v1/config
- POST /api/v1/sessions
- GET /api/v1/sessions
- GET /api/v1/sessions/{session_id}
- POST /api/v1/sessions/{session_id}/messages
- POST /api/v1/artifacts
- POST /api/v1/sessions/{session_id}/ship30

## 4. Ingestion and retrieval flow
1. The app scans the transcript directory for local text files.
2. Each file is split into paragraphs and chunked into smaller sections.
3. During a query, the app ranks chunks using token overlap against the incoming question.
4. The best matches are passed into the prompt as transcript context.
5. The answer generation step is strict: if no chunk is relevant, the app explains that the transcript set cannot support the claim.

## 5. Agent routing and model toggle
The configuration layer reads settings from environment variables. The app defaults to Ollama but allows OpenAI or Anthropic keys to be set. A `provider_status` check decides whether the selected provider is healthy; if not, the app falls back to the mock provider instead of crashing.

## 6. Artifact generation and security
Artifact generation uses a markdown-first workflow and then converts to HTML for in-app rendering. Before serving, the HTML is sanitized with `bleach` and rendered inside a sandboxed iframe. This reduces XSS risk by blocking script tags and unsafe attributes while still allowing headings, lists, emphasis, code blocks, and links.

## 7. Deployment topology
The app can be started with Docker Compose. One service runs Postgres and another runs the API. Ollama is intentionally left outside the container because it is a local model runtime that is easiest to run on the host machine.

## 8. Observability and resilience
The app uses structured logs for model provider calls, retrieval attempts, DB health checks, and artifact generation. Missing keys, empty retrieval results, timeouts, and Postgres issues degrade gracefully without crashing the request path.
