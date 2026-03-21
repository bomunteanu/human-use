# human-use MCP server

MCP server that connects AI agents to the [Rapidata](https://rapidata.ai) human intelligence API. Also ships a web research agent with a React frontend.

## Running

### MCP server
```bash
uv run human-use
```

### Web research backend
```bash
uv run uvicorn human_use.api:app --reload
```

### Frontend
```bash
cd frontend && npm run dev
```

Requires a `.env` file with:
```
RAPIDATA_CLIENT_ID=...
RAPIDATA_CLIENT_SECRET=...
```

## Architecture

```
src/human_use/
├── server.py   # FastMCP setup and tool registration
├── tools.py    # Tool implementations (async, typed)
├── models.py   # Pydantic result types + SSE event models + TargetingConfig
├── agent.py    # Claude-powered research agent loop
├── api.py      # FastAPI: POST /research/stream, POST /research/answer
└── client.py   # RapidataClient singleton + run_sync helper

frontend/src/
├── App.tsx
├── types.ts
├── hooks/useResearchStream.ts
└── components/
    ├── ThoughtStream.tsx
    ├── ClarifyingQuestion.tsx
    ├── OrdersPanel.tsx
    ├── TargetingSelector.tsx
    ├── BriefPdfPanel.tsx
    └── ResearchPdfDocument.tsx
```

## MCP Tools

| Tool | Signature | Returns |
|---|---|---|
| `ask_clarifying_question` | `(question, options)` | `answer: str` (web frontend only) |
| `ask_free_text` | `(question, n, language?, targeting?)` | `order_id: str` |
| `ask_multiple_choice` | `(question, options, n, language?, targeting?)` | `order_id: str` |
| `compare` | `(question, option_a, option_b, n, language?, targeting?)` | `order_id: str` |
| `rank` | `(question, items, n, language?, targeting?)` | `order_id: str` |
| `check_progress` | `(order_id)` | `ProgressResult` |
| `get_results` | `(order_id)` | `FreeTextResult \| MultipleChoiceResult \| CompareResult \| RankResult` |

Dispatch tools return immediately. Fetch results separately.

## Geographic Targeting

All dispatch tools accept an optional `targeting: TargetingConfig` argument. `TargetingConfig` is defined in `models.py`:

```python
class TargetingConfig(BaseModel):
    country_codes: list[str]  # ISO 3166-1 alpha-2; empty = Worldwide (no filter)
```

When `country_codes` is non-empty, a `CountryFilter` is added to the Rapidata order alongside any language filter. Worldwide = no `CountryFilter` applied.

The frontend `TargetingSelector` component exposes countries grouped by continent. The selection is passed to `POST /research/stream` as repeated `country_codes` query parameters (e.g. `?country_codes=US&country_codes=DE`). The API builds a `TargetingConfig` and threads it through `run_agent` → `_dispatch` → each tool call.

## Web Research Agent

`POST /research/stream` accepts `{question, session_id}` (body) + optional `country_codes` (query params) and returns an SSE stream. The agent (Claude Sonnet) runs in three phases:

1. **CLARIFY** — asks at most 3 clarifying questions via `ask_clarifying_question` before dispatching any surveys
2. **SURVEY** — dispatches up to 5 Rapidata orders, polls for results
3. **BRIEF** — calls `complete_research` to emit a structured research brief

### Clarifying question flow

- Agent calls `ask_clarifying_question(question, options)` — emits a `clarifying_question` SSE event
- Frontend renders the question with 4 buttons (3 options + "Other (please specify)")
- User selects an answer → frontend POSTs `{session_id, question_index, answer}` to `POST /research/answer`
- Backend resolves an `asyncio.Event` keyed by `(session_id, question_index)`; agent unblocks and receives the answer as its tool result
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
| `done` | `brief: {question, sections, summary}` |

## PDF Preview Panel

The right panel renders a live PDF via `@react-pdf/renderer`. As `brief_update` events arrive, new sections appear in the PDF in real time. When `done` fires, an **Export PDF** button activates.

### Chart embedding

When an `order_complete` event fires for an order with distribution data, `OrdersPanel` captures the recharts bar chart as a PNG:

1. `querySelector('svg')` on the chart wrapper div
2. `XMLSerializer` → SVG string → `Blob` URL
3. Draw into an offscreen `<canvas>` at 2× resolution (white background)
4. `canvas.toDataURL('image/png')` → stored in `svgCaptures: Map<string, string>` in `App.tsx`
5. Passed to `ResearchPdfDocument` as `<Image src={pngDataUrl} />`

SVG data URLs are not used directly because react-pdf's image renderer is unreliable with complex SVGs (`<clipPath>`, `<defs>`, CSS in recharts output).

### Markdown rendering

`section.content` from the agent brief is markdown. `ResearchPdfDocument` parses it in two passes:
- **Block**: lines starting with `- `/`* ` → bullet rows; `## ` → subheadings; otherwise paragraph
- **Inline**: `**bold**` / `*italic*` → nested `<Text>` with `Helvetica-Bold` / `Helvetica-Oblique`

### Vite config note

`@react-pdf/renderer` requires `optimizeDeps: { include: ['@react-pdf/renderer'] }` in `vite.config.ts` to avoid ESM pre-bundling errors. `react-is` (a recharts peer dep) also needs to be listed there.

## Key invariants

- `responses_per_datapoint` is hardcoded to `10` everywhere — not configurable
- All blocking SDK calls go through `run_sync()` in `client.py`, which wraps them with `asyncio.to_thread`
- `run_sync()` also redirects stdout → stderr during SDK calls. **Do not remove this.** The Rapidata SDK prints status messages to stdout (e.g. `"Order 'mc::...' is now viewable under: ..."`), which corrupts the MCP stdio transport if they reach stdout
- Order type is encoded in the order name prefix: `ft::`, `mc::`, `cmp::`, `rnk::` — `get_results` uses this prefix to determine how to parse the result DataFrame
- Survey cap: `MAX_SURVEYS = 5` (hard cap via error tool result + soft cap via system prompt)
- Clarification cap: `MAX_CLARIFICATIONS = 3` (hard cap via error tool result)
- `ask_clarifying_question` in `tools.py` raises `NotImplementedError` — the real blocking logic lives in `agent.py` via `asyncio.Event`

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
