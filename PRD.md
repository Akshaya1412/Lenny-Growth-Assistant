# Product Requirements Document: The Lenny Growth Assistant

## 1. Discovery brief

### User and problem
The primary user is an internal product and growth team member who wants fast, grounded answers about Lenny’s podcast and newsletter themes without manually reading transcripts or crafting prompts. Their job is to synthesize product, customer, and growth lessons into strategy decisions, launch ideas, and usable communication. The assistant removes the manual research burden and replaces it with a traceable, source-grounded answer that still feels conversational.

### Success metric
One measurable product metric is a 90%+ answer grounding rate: chat responses should cite or clearly tie back to transcript sources. One operational metric is a 95% successful startup rate after a standard local setup, plus a failure mode that still allows the app to answer in a degraded fallback while clearly describing the limitation.

### Assumptions
- The transcript corpus is a curated internal dataset, not a full real-time news or web feed.
- The primary evaluation is a local demo, not a large-scale production deployment.
- Users are comfortable working in a browser and do not need a custom auth system for this exercise.
- Because the brief does not specify a complete transcript repository, the app includes a local transcript ingestion path and can be extended to a real corpus later.

### Scope choices
Included:
- FastAPI backend with persistent session storage
- Local transcript ingestion and basic retrieval
- LLM switching with local Ollama as the default and cloud fallback
- Chat UX with artifact preview and source-grounded responses
- Hand-off docs and test coverage

Excluded:
- Full multi-user auth and RBAC
- Real-time streaming or WebSocket collaboration
- Large-scale semantic search infrastructure or vector databases
- Public deployment to a managed hosting service beyond the local Docker workflow

Why:
- The assignment is an internal, evaluator-focused demo. The product needs to be understandable, testable, and resilient in a local environment rather than overbuilt for scale.

### Risks and trade-offs
- Hallucination: mitigated with transcript-first grounding and transparent citations
- Latency: reduced with small retrieval windows and a fallback provider
- Cost: local Ollama is preferred for the demo; cloud is optional and configured by env vars
- Data leakage: prompt logs are kept in a local Postgres demo and the app clearly labels source constraints
- Unsafe artifact rendering: sanitized HTML is served inside a sandboxed iframe to limit script execution

## 2. User flows
1. Create a session and ask a question about product strategy or growth.
2. The app retrieves relevant transcript chunks.
3. The assistant answers with source names and cites them in the UI.
4. The user asks a follow-up or requests a generated artifact.
5. The app produces an HTML or Markdown artifact and renders it beside the chat.

## 3. Acceptance criteria
- A user can start a new chat and continue within a session.
- The assistant answers with sources from the loaded transcript set.
- The app responds gracefully when there are no retrieval matches.
- The app can switch providers via config without code changes.
- A generated artifact renders in-app without raw HTML injection.
- The project runs via documented setup commands and includes tests.

## 4. Implementation plan
1. Create a simple, reliable backend and storage model.
2. Ingest local transcripts, split them into chunks, and index them in memory with basic ranking.
3. Add a grounding layer that passes retrieval context into the model and instructs strict source adherence.
4. Add chat sessions, retrieval, and artifact generation.
5. Build the browser UI and artifact viewer.
6. Validate the system with tests and a manual UI playbook.
