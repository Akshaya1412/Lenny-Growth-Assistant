# Agent transcript: Lenny Growth Assistant

## Attempt 1
The initial approach was to build an over-engineered vector database pipeline. That made the project harder to run locally and harder to explain to an evaluator.

### Failure mode
The retrieval stack was too heavy for a small demo and introduced extra dependencies without adding much value for the assignment.

### Fix
We simplified the architecture to local transcript ingestion and lightweight token-overlap retrieval. This keeps the system grounded and easy to test while preserving a clear source trail.

## Attempt 2
The first artifact viewer was designed to display raw HTML strings directly in the page. That is unsafe and weakly isolated.

### Failure mode
Untrusted HTML can execute scripts or import external resources.

### Fix
We moved to a sanitized HTML path and sandboxed iframe rendering. This keeps the viewer capable while reducing risk from generated markup.

## Attempt 3
The first model route assumed the selected provider always worked.

### Failure mode
Local Ollama is not guaranteed to be running in a fresh environment.

### Fix
We added provider health checks and graceful fallback so the application still responds with a clear degraded-mode answer when the model layer is unavailable.

## Final decision
The application now prioritizes source-grounding, simple architecture, and operational clarity over maximum model sophistication. That is the right trade-off for a forward-deployed internal demo with a limited evaluation window.
