# human-use MCP server

MCP server that connects AI agents to the [Rapidata](https://rapidata.ai) human intelligence API. Also ships a web research agent with a React frontend.

## Running

### All-in-one (Docker Compose)
```bash
docker compose up --build
```
- Frontend: http://localhost:80
- Backend API: http://localhost:8000
- Postgres: localhost:5432

Reads all credentials from `.env` via `env_file`. Overrides `DATABASE_URL` to point at the `db` service automatically.

### MCP server
```bash
uv run human-use
```

### Web research backend (local dev)
```bash
docker compose up -d db   # start Postgres only
uv run uvicorn human_use.api:app --reload
```

### Frontend (local dev)
```bash
cd frontend && npm run dev
```

Requires a `.env` file with:
```
RAPIDATA_CLIENT_ID=...
RAPIDATA_CLIENT_SECRET=...
ANTHROPIC_API_KEY=...
DATABASE_URL=postgresql+asyncpg://humanuse:humanuse@localhost:5432/humanuse
JWT_SECRET=...
```

## Architecture

```
src/human_use/
├── server.py   # FastMCP setup and tool registration
├── tools.py    # Tool implementations (async, typed)
├── models.py   # Pydantic result types + SSE event models + TargetingConfig
├── agent.py    # Claude-powered research agent loop + run_compile
├── api.py      # FastAPI: POST /research/stream, POST /research/answer, POST /research/compile
└── client.py   # RapidataClient singleton + run_sync helper

frontend/src/
├── App.tsx                          # Root: ResearchProvider + 3-column layout shell
├── types.ts                         # SSE event types, OrderState, ChatMessage union, AnthropicMessage
├── store.ts                         # Zustand store: all state + SSE streaming logic
├── context/
│   └── ResearchContext.tsx          # Thin shim: useResearchContext() maps Zustand store to legacy API
├── hooks/
│   └── useResearchStream.ts         # Legacy (unused by new UI; kept for reference)
└── components/
    ├── Sidebar.tsx                  # Session history list + New Research + Reports button
    ├── ChatPane.tsx                 # Chat area: owns inputText/countryCodes state; computes showThinking
    ├── ChatMessageList.tsx          # Renders AnimatedMessageWrapper per ChatMessage + ThinkingBubble
    ├── AnimatedMessageWrapper.tsx   # Fade+slide entry animation (first mount only)
    ├── UserMessageBubble.tsx        # Right-aligned user message bubble
    ├── AgentThoughtBubble.tsx       # Left-aligned agent thought (react-markdown)
    ├── ThinkingBubble.tsx           # Three-dot bounce animation; shown while agent synthesises
    ├── SurveyResultCard.tsx         # Left-aligned survey card; SVG→PNG capture
    ├── ClarifyingQuestionBubble.tsx # Left-aligned Q with 4 buttons; answered state
    ├── ChatInputBar.tsx             # Input row: TargetingSelector + Send + Compile
    ├── PdfPanel.tsx                 # Collapsible right panel; owns zoom state
    ├── PdfToolbar.tsx               # Close, zoom controls, export button
    ├── ResearchPdfDocument.tsx      # react-pdf Document; markdown + table renderer
    ├── ArtifactsPanel.tsx           # Reports panel: lists completed sessions with Open/Download per entry
    ├── TargetingSelector.tsx        # Country/continent dropdown (opens upward)
    └── ui/                          # Radix UI wrappers (Button, Card, etc.)
```

## MCP Tools

| Tool | Signature | Returns |
|---|---|---|
| `ask_clarifying_question` | `(question, options)` | `answer: str` (web frontend only) |
| `ask_free_text` | `(question, n, targeting?)` | `order_id: str` |
| `ask_multiple_choice` | `(question, options, n, targeting?)` | `order_id: str` |
| `compare` | `(question, option_a, option_b, n, targeting?)` | `order_id: str` |
| `rank` | `(question, items, n, targeting?)` | `order_id: str` |
| `check_progress` | `(order_id)` | `ProgressResult` |
| `get_results` | `(order_id)` | `FreeTextResult \| MultipleChoiceResult \| CompareResult \| RankResult` |

Dispatch tools return immediately. Fetch results separately.

`ask_multiple_choice` silently caps `options` to 8 (Rapidata API limit). The tool schema also declares `maxItems: 8` to discourage the LLM from exceeding the limit.

## Geographic Targeting

All dispatch tools accept an optional `targeting: TargetingConfig` argument. `TargetingConfig` is defined in `models.py`:

```python
class TargetingConfig(BaseModel):
    country_codes: list[str]  # ISO 3166-1 alpha-2; empty = Worldwide (no filter)
```

When `country_codes` is non-empty, a `CountryFilter` is added to the Rapidata order. Worldwide = no `CountryFilter` applied. No language filter is ever applied — surveys go out to respondents of any language.

The frontend `TargetingSelector` component exposes countries grouped by continent. The selection is passed to `POST /research/stream` as repeated `country_codes` query parameters (e.g. `?country_codes=US&country_codes=DE`). The API builds a `TargetingConfig` and threads it through `run_agent` → `_dispatch` → each tool call.

## Web Research Agent

`POST /research/stream` accepts `{question, session_id, messages?}` (body) + optional `country_codes` (query params) and returns an SSE stream. The `messages` field carries the full Anthropic-format conversation history from prior sessions (empty list for a fresh start). The agent (Claude Sonnet) runs in three phases:

1. **CLARIFY** — asks at most 3 clarifying questions via `ask_clarifying_question` before dispatching any surveys
2. **SURVEY** — dispatches up to 1 Rapidata order (`MAX_SURVEYS = 1`), polls for results
3. **BRIEF** — calls `complete_research` to emit a structured research brief

When `messages` is non-empty (continuation session) the system prompt switches to **CONTINUATION MODE**, instructing the agent to synthesise findings across all prior sessions in its `complete_research` brief.

### Compile endpoint

`POST /research/compile` accepts `{session_id, messages}` and streams `brief_update` + `done` events. It runs a single forced `complete_research` call (no survey tools available) over the full conversation history — a read-only synthesis pass that does not add to the conversation history stored on the frontend.

### Clarifying question flow

- Agent calls `ask_clarifying_question(question, options)` — emits a `clarifying_question` SSE event
- Frontend renders the question bubble with 4 buttons (3 options + "Other (please specify)")
- User selects an answer → frontend POSTs `{session_id, question_index, answer}` to `POST /research/answer`
- Backend resolves an `asyncio.Event` keyed by `(session_id, question_index)`; agent unblocks and receives the answer as its tool result
- The bubble stays in the chat showing the chosen answer (`answeredWith` field); no removal
- Session state is cleaned up when the SSE stream closes

### SSE event types

| Event | Key fields |
|---|---|
| `clarifying_question` | `session_id`, `question_index`, `question`, `options` (always 4) |
| `agent_thought` | `text` |
| `order_dispatched` | `order_id`, `tool`, `question` |
| `order_progress` | `order_id`, `status`, `is_complete` |
| `order_complete` | `order_id`, `distribution`, `winner`, `n_responses` |
| `brief_update` | `section: {title, content}` |
| `done` | `brief: {question, title, sections, summary}`, `messages: AnthropicMessage[]` |

`agent_thought` is emitted with the `complete_research` summary text just before the `brief_update` stream, so it appears as a plain-language conclusion bubble in the chat.

`done.messages` contains the complete serialisable Anthropic conversation history for the session. The frontend stores this and sends it back as `messages` in the next `POST /research/stream` request.

### Conversation history invariant

Every `done.messages` array is a valid Anthropic conversation: the final assistant message containing a `complete_research` `tool_use` block is immediately followed by a synthetic user message with a `tool_result` acknowledging completion. Without this closing pair the Anthropic API rejects the next request with a 400 ("tool_use ids found without tool_result blocks").

## Frontend State Architecture

All state lives in a **Zustand store** (`store.ts`). `ResearchContext.tsx` is now a thin shim — `useResearchContext()` maps the Zustand store fields to the legacy `{ state, dispatch, startResearch, … }` shape so no component imports needed to change. `ResearchProvider` is a no-op wrapper (`<>{children}</>`).

### Store shape

```typescript
interface ResearchStore {
  conversationHistory: AnthropicMessage[];  // sent to backend on every request
  chatMessages: ChatMessage[];              // rendered in chat pane (persists across sessions)
  sessionId, isStreaming, isDone, error, currentQuestion,
  orders: Map<string, OrderState>,
  chartCaptures: Map<string, string>,
  sections, brief, isPdfPanelOpen,
  _abortController,

  startResearch(question, countryCodes?)   // appends to chatMessages, keeps conversationHistory
  compileFindings()                        // POSTs conversationHistory to /research/compile
  stopResearch, submitAnswer, setChartCapture,
  openPdfPanel, closePdfPanel, reset,
}
```

`chatMessages` is **never reset** between sessions — follow-up questions append to the existing timeline so the user can scroll back through all prior turns. `orders`, `sections`, and `brief` reset at the start of each new research session.

### AnthropicMessage type

`types.ts` exports:

```typescript
type AnthropicContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_use"; id: string; name: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool_use_id: string; content: string; is_error?: boolean };

interface AnthropicMessage {
  role: "user" | "assistant";
  content: string | AnthropicContentBlock[];
}
```

### ChatMessage union type

Every item in the chat timeline is a `ChatMessage` (defined in `types.ts`):

```typescript
type ChatMessage =
  | { type: "user_message";        id, text, timestamp }
  | { type: "agent_thought";       id, text, timestamp }          // markdown
  | { type: "survey_result";       id, order: OrderState, chartCapture: string|null, timestamp }
  | { type: "clarifying_question"; id, sessionId, questionIndex, question, options, answeredWith: string|null, timestamp }
```

### SSE event → state mapping

| SSE event | Store effect |
|---|---|
| `clarifying_question` | push `ClarifyingQuestion` message |
| `agent_thought` | push `AgentThought` message |
| `order_dispatched` | add to `orders` Map **and** push `SurveyResult` message (`is_complete: false`) |
| `order_progress` | update `orders` Map + update matching `SurveyResult` message in-place |
| `order_complete` | update `orders` Map + update matching `SurveyResult` message in-place |
| `brief_update` | push to `sections`; set `isPdfPanelOpen = true` |
| `done` | set `isDone = true`, `isStreaming = false`, `brief`; update `conversationHistory` from `evt.messages` |

Survey bubbles appear immediately on `order_dispatched` showing an in-progress skeleton, then transition to the chart view when `order_complete` arrives.

### Thinking bubble

`ChatPane` computes `showThinking` from existing store state (no extra field):

```typescript
const showThinking =
  state.isStreaming &&
  state.orders.size > 0 &&
  [...state.orders.values()].every(o => o.is_complete) &&
  !hasSections;
```

This is `true` exactly during the gap between the last `order_complete` and the first `brief_update` (i.e. while the LLM is writing the report). `ChatMessageList` renders `ThinkingBubble` — three dots with staggered `animate-bounce` — when `showThinking` is true.

## Chat UI Layout

Three-column layout: `Sidebar (240px) | ChatPane (flex-1) | PdfPanel (440px, collapsible)`.

- **Sidebar** — "New Research" button (resets state) + live session history (loaded from `GET /sessions`) + "Reports" button (opens ArtifactsPanel, shows count badge of completed sessions)
- **ChatPane** — scrollable `ChatMessageList` + `ChatInputBar` pinned to bottom
- **ChatInputBar** — `TargetingSelector` (opens upward) + textarea + Send/Stop + Compile Findings / View Brief
  - "Compile Findings" — stops any running stream then POSTs conversation history to `/research/compile`
  - "View Brief" shown after streaming ends when sections exist — reopens PDF panel
- **PdfPanel** — never unmounted; CSS `width` transition compresses the chat pane; owns `zoom` state (0.5–2.0, step 0.25)
- **ArtifactsPanel** — slides in from the right (same 440px column as PdfPanel, mutually exclusive); lists all sessions with a non-null `brief`; each row has Open (loads session + opens PDF) and Download (client-side PDF via `PDFDownloadLink`) buttons

## PDF Preview Panel

The right panel renders a live PDF via `@react-pdf/renderer`. As `brief_update` events arrive, new sections appear in the PDF in real time. When `done` fires, the **Export** button activates.

The PDF title is the LLM-supplied `brief.title` (from the `complete_research` tool call), falling back to `currentQuestion`. The filename mirrors the title.

### Chart embedding

When an `order_complete` event fires for an order with distribution data, `SurveyResultCard` captures the recharts bar chart as a PNG:

1. `querySelector('svg')` on the chart wrapper div
2. `XMLSerializer` → SVG string → `Blob` URL
3. Draw into an offscreen `<canvas>` at 2× resolution (white background)
4. `canvas.toDataURL('image/png')` → dispatched via `setChartCapture` → stored in `chartCaptures: Map<string, string>` in the store
5. Passed to `ResearchPdfDocument` as `<Image src={pngDataUrl} />`

SVG data URLs are not used directly because react-pdf's image renderer is unreliable with complex SVGs (`<clipPath>`, `<defs>`, CSS in recharts output).

**Capture retry**: `recharts` uses `ResizeObserver` to size its SVG asynchronously. The capture effect retries up to 10 times with 150 ms gaps if `getBoundingClientRect().width === 0`.

### Markdown rendering

`section.content` from the agent brief is markdown. `ResearchPdfDocument` uses a `while`-loop block parser (not a simple `forEach`) so it can look ahead and group consecutive lines:

- **Tables**: consecutive lines starting with `|` are grouped, the separator row (`---`) is stripped, and rendered as a bordered `View` grid with `Helvetica-Bold` headers
- **Bullets**: lines starting with `- ` or `* ` → `bulletRow` with fixed-width dot wrapper
- **Subheadings**: lines starting with `#` → `subheading` style
- **Paragraphs**: everything else
- **Inline**: `**bold**` / `*italic*` → nested `<Text>` with `Helvetica-Bold` / `Helvetica-Oblique`

Bullet dot `•` is wrapped in a `<View style={{ width: 14, flexShrink: 0 }}>` — a bare `<Text width={14}>` is ignored by react-pdf's flex engine and causes the dot to overlap the text.

### Vite config note

`@react-pdf/renderer` requires `optimizeDeps: { include: ['@react-pdf/renderer'] }` in `vite.config.ts` to avoid ESM pre-bundling errors. `react-is` (a recharts peer dep) also needs to be listed there.

## Key invariants

- `responses_per_datapoint` is hardcoded to `50` everywhere — not configurable
- `ask_multiple_choice` caps options to 8 before calling Rapidata (API limit)
- All blocking SDK calls go through `run_sync()` in `client.py`, which wraps them with `asyncio.to_thread`
- `run_sync()` also redirects stdout → stderr during SDK calls. **Do not remove this.** The Rapidata SDK prints status messages to stdout (e.g. `"Order 'mc::...' is now viewable under: ..."`), which corrupts the MCP stdio transport if they reach stdout
- Order type is encoded in the order name prefix: `ft::`, `mc::`, `cmp::`, `rnk::` — `get_results` uses this prefix to determine how to parse the result DataFrame
- Survey cap: `MAX_SURVEYS = 1` (hard cap via error tool result + soft cap via system prompt)
- Clarification cap: `MAX_CLARIFICATIONS = 3` (hard cap via error tool result)
- `ask_clarifying_question` in `tools.py` raises `NotImplementedError` — the real blocking logic lives in `agent.py` via `asyncio.Event`
- `done.messages` must always end with a synthetic `tool_result` for `complete_research` — see "Conversation history invariant" above

## Result parsing

`get_results` calls `order.get_results().to_pandas()` and parses the DataFrame by order name prefix. Column selection is heuristic:

- `ft::` — looks for columns named `response`, `answer`, `text`, `result`; falls back to last column
- `mc::` — reads `aggregatedResults_<option>` columns (integer vote counts per option)
- `cmp::` — reads `A_*` / `B_*` columns from `_compare_to_pandas()`; falls back to last two numeric columns
- `rnk::` — bypasses `to_pandas()` entirely; reads `raw["results"][*]["aggregatedResults"]` as `{item: elo_score}` dict

If a real API response doesn't match, adjust the column detection in `tools.py:get_results`.

## Tests

```bash
uv run pytest
```

All tests mock `RapidataClient` and `anthropic.AsyncAnthropic` entirely — no real API calls.

Tests for the clarifying question flow pre-populate `_pending_answers` before starting the SSE stream (rather than making concurrent requests) because `httpx.ASGITransport` buffers the entire response before returning it — making a concurrent POST from inside the stream reader would deadlock.

`test_api.py` also covers:
- `done` event carries a non-empty `messages` array
- Prior messages are prepended to the Anthropic API call on follow-up requests
- `/research/compile` emits `brief_update` + `done` and passes the full history to the model

## MCP client config

```json
{
  "mcpServers": {
    "human-use": {
      "command": "uv",
      "args": ["--directory", "/path/to/human-use", "run", "human-use"]
    }
  }
}
```

Use the full path to `uv` if the client doesn't find it (e.g. `/Users/you/.cargo/bin/uv`).
