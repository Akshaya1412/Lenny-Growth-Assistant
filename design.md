# Design

## 1. UI/UX principles
The interface needs to feel like an internal product assistant, not an experimental prompt playground. The user should feel one step away from a useful answer and one step away from a reusable artifact.

### Core design decisions
- A left sidebar keeps session management visible and lightweight.
- A center chat stream emphasizes conversation flow and grounding.
- A right panel renders generated artifacts beside the chat to mirror a Claude-style artifacts workflow.
- The default experience stays simple: ask a question, review a grounded answer, and generate a document when needed.

## 2. Information architecture
- Session list: persistent conversation history.
- Chat panel: user and assistant messages with citations.
- Model selector: visible because provider switching is part of the evaluator experience.
- Artifact viewer: sanitized HTML in an iframe with a sandbox.

## 3. Interaction states
- Empty state: default guidance to ask a product or growth question.
- Busy state: send button stays active and the app shows the current assistant response when it returns.
- Retrieval miss: answer explicitly says the transcript set did not contain sufficient support.
- Provider fallback: UI can still continue using mock mode and displays provider status from the config endpoint.

## 4. Responsive behavior
- Desktop: three-column layout with session list, conversation, and artifact viewer.
- Tablet: conversation and viewer stack vertically while keeping the sidebar available.
- Mobile: the chat stays primary and the viewer stacks below the conversation.

## 5. Accessibility considerations
- Semantic form controls and labels are used.
- The chat stream is announced as live content using an aria-live region.
- The artifact iframe should remain readable using a simple, high-contrast stylesheet.
- Buttons have sufficient color contrast and visible focus states.

## 6. Design trade-offs
The app purposely prefers clarity over complexity. It does not include a rich markdown editor or collaboration layer because the assignment is about grounded writing, retrieval, and local deployability rather than a broad product suite.
