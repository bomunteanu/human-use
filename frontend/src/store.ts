import { create } from "zustand";
import type {
  AgentThought,
  AnthropicMessage,
  BriefSection,
  ChatMessage,
  ClarifyingQuestion,
  OrderState,
  ResearchBrief,
  SessionSummary,
  SSEEvent,
  SurveyResult,
  TargetingConfig,
  UserMessage,
} from "./types";
import { emptyTargeting } from "./types";

// ─── State shape ──────────────────────────────────────────────────────────────

export interface ResearchStore {
  /** Anthropic-format conversation history — sent verbatim to the backend on each request */
  conversationHistory: AnthropicMessage[];

  sessionId: string | null;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
  currentQuestion: string;

  /** UI chat messages rendered in the chat pane */
  chatMessages: ChatMessage[];
  orders: Map<string, OrderState>;
  chartCaptures: Map<string, string>;

  sections: BriefSection[];
  brief: ResearchBrief | null;
  isPdfPanelOpen: boolean;
  currentTargeting: TargetingConfig;

  _abortController: AbortController | null;

  // ─── Auth ────────────────────────────────────────────────────────────────────
  authToken: string | null;

  // ─── Session history ─────────────────────────────────────────────────────────
  sessionHistory: SessionSummary[];
  isLoadingSessions: boolean;
  isArtifactsOpen: boolean;

  // ─── Actions ──────────────────────────────────────────────────────────────

  startResearch: (question: string, targeting?: TargetingConfig) => void;
  setTargeting: (targeting: TargetingConfig) => void;
  compileFindings: () => void;
  stopResearch: () => void;
  submitAnswer: (questionIndex: number, answer: string) => void;
  setChartCapture: (orderId: string, dataUrl: string) => void;
  openPdfPanel: () => void;
  closePdfPanel: () => void;
  reset: () => void;
  /** Internal — apply a single SSE event to the store */
  _applySSEEvent: (evt: SSEEvent) => void;

  // ─── Auth actions ─────────────────────────────────────────────────────────
  setAuthToken: (token: string | null) => void;

  // ─── Session history actions ───────────────────────────────────────────────
  fetchSessions: () => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  renameSession: (sessionId: string, title: string) => Promise<void>;
  openArtifacts: () => void;
  closeArtifacts: () => void;
}

// ─── SSE chunk parser ─────────────────────────────────────────────────────────

function* parseSSEChunk(chunk: string): Generator<SSEEvent> {
  const normalized = chunk.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  for (const block of normalized.split(/\n\n+/)) {
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("data:")) {
        data += line.slice(5).trimStart();
      }
    }
    if (!data) continue;
    try {
      yield JSON.parse(data) as SSEEvent;
    } catch {
      // ignore malformed
    }
  }
}

// ─── Shared SSE streaming helper ──────────────────────────────────────────────

async function streamSSE(
  url: string,
  body: object,
  signal: AbortSignal,
  extraHeaders: Record<string, string>,
  onEvent: (evt: SSEEvent) => void,
  onError: (msg: string) => void,
  onDone: () => void,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...extraHeaders },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    onError("Connection lost.");
    return;
  }

  if (res.status === 401) {
    localStorage.removeItem("jwt");
    window.location.reload();
    return;
  }

  if (!res.ok || !res.body) {
    onError(`HTTP ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

      const boundary = buffer.lastIndexOf("\n\n");
      if (boundary === -1) continue;

      const complete = buffer.slice(0, boundary + 2);
      buffer = buffer.slice(boundary + 2);

      for (const event of parseSSEChunk(complete)) {
        onEvent(event);
      }
    }

    for (const event of parseSSEChunk(buffer)) {
      onEvent(event);
    }
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    onError("Connection lost.");
    return;
  }

  onDone();
}

// ─── Store ────────────────────────────────────────────────────────────────────

const INITIAL_STATE = {
  conversationHistory: [] as AnthropicMessage[],
  sessionId: null as string | null,
  isStreaming: false,
  isDone: false,
  error: null as string | null,
  currentQuestion: "",
  chatMessages: [] as ChatMessage[],
  orders: new Map<string, OrderState>(),
  chartCaptures: new Map<string, string>(),
  sections: [] as BriefSection[],
  brief: null as ResearchBrief | null,
  isPdfPanelOpen: false,
  currentTargeting: emptyTargeting() as TargetingConfig,
  _abortController: null as AbortController | null,
};

export const useStore = create<ResearchStore>((set, get) => ({
  ...INITIAL_STATE,
  authToken: localStorage.getItem("jwt"),
  sessionHistory: [] as SessionSummary[],
  isLoadingSessions: false,
  isArtifactsOpen: false,

  // ─── setAuthToken ────────────────────────────────────────────────────────────

  setAuthToken: (token) => {
    if (token) {
      localStorage.setItem("jwt", token);
    } else {
      localStorage.removeItem("jwt");
    }
    set({ authToken: token });
  },

  // ─── fetchSessions ───────────────────────────────────────────────────────────

  fetchSessions: async () => {
    const { authToken } = get();
    if (!authToken) return;
    set({ isLoadingSessions: true });
    try {
      const res = await fetch("http://localhost:8000/sessions", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) {
        if (res.status === 401) {
          get().setAuthToken(null);
        }
        return;
      }
      const data: SessionSummary[] = await res.json();
      set({ sessionHistory: data });
    } catch {
      // network error — silently ignore
    } finally {
      set({ isLoadingSessions: false });
    }
  },

  // ─── loadSession ─────────────────────────────────────────────────────────────

  loadSession: async (sessionId) => {
    const { authToken } = get();
    if (!authToken) return;

    const res = await fetch(`http://localhost:8000/sessions/${sessionId}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    if (!res.ok) return;

    const data: {
      id: string;
      title: string;
      brief: ResearchBrief | null;
      messages: AnthropicMessage[];
    } = await res.json();

    // ── Pass 1: gather all dispatch tool_use blocks and their returned order_ids ──
    // Maps tool_use.id → { orderId, tool, question }
    const dispatchTools = new Set(["ask_multiple_choice", "ask_free_text", "compare", "rank"]);
    const dispatchById = new Map<string, { tool: string; question: string }>();
    const orderById = new Map<string, OrderState>(); // keyed by order_id

    for (let i = 0; i < data.messages.length; i++) {
      const msg = data.messages[i];
      if (msg.role !== "assistant" || !Array.isArray(msg.content)) continue;
      for (const block of msg.content) {
        if (block.type !== "tool_use" || !dispatchTools.has(block.name)) continue;
        dispatchById.set(block.id, {
          tool: block.name,
          question: (block.input as Record<string, unknown>).question as string ?? "",
        });
        // The corresponding tool_result in the next user message has the order_id
        const nextMsg = data.messages[i + 1];
        if (!nextMsg || nextMsg.role !== "user" || !Array.isArray(nextMsg.content)) continue;
        for (const rb of nextMsg.content) {
          if (rb.type !== "tool_result" || rb.tool_use_id !== block.id) continue;
          const orderId = typeof rb.content === "string" ? rb.content.trim() : "";
          if (!orderId) continue;
          orderById.set(orderId, {
            order_id: orderId,
            tool: block.name,
            question: (block.input as Record<string, unknown>).question as string ?? "",
            status: "complete",
            is_complete: true,
            distribution: null,
            winner: null,
            n_responses: null,
            country_counts: {},
          });
        }
      }
    }

    // ── Pass 2: fill in distribution from get_results tool_results ─────────────
    for (let i = 0; i < data.messages.length; i++) {
      const msg = data.messages[i];
      if (msg.role !== "assistant" || !Array.isArray(msg.content)) continue;
      for (const block of msg.content) {
        if (block.type !== "tool_use" || block.name !== "get_results") continue;
        const orderId = (block.input as Record<string, unknown>).order_id as string;
        const nextMsg = data.messages[i + 1];
        if (!nextMsg || nextMsg.role !== "user" || !Array.isArray(nextMsg.content)) continue;
        for (const rb of nextMsg.content) {
          if (rb.type !== "tool_result" || rb.tool_use_id !== block.id) continue;
          try {
            const result = JSON.parse(typeof rb.content === "string" ? rb.content : JSON.stringify(rb.content));
            const order = orderById.get(orderId);
            if (!order) continue;
            // MultipleChoiceResult: { options: {opt: count}, winner, n_responses }
            // CompareResult:        { scores: {opt: score}, winner, n_responses }
            const distribution: Record<string, number> | null =
              result.options ?? result.scores ?? null;
            orderById.set(orderId, {
              ...order,
              distribution,
              winner: result.winner ?? null,
              n_responses: result.n_responses ?? null,
            });
          } catch {
            // malformed tool_result — skip
          }
        }
      }
    }

    // ── Pass 3: build chat messages in conversation order ──────────────────────
    const chatMessages: ChatMessage[] = [];
    // Track which order_ids we've already emitted a survey bubble for
    const emittedOrders = new Set<string>();

    for (let i = 0; i < data.messages.length; i++) {
      const msg = data.messages[i];

      if (msg.role === "user") {
        const content = msg.content;
        if (typeof content === "string") {
          const text = content.replace(/^Research question:\s*/i, "").split("\n")[0].trim();
          if (text) {
            chatMessages.push({
              id: crypto.randomUUID(),
              type: "user_message",
              text,
              timestamp: i,
            });
          }
        }
        // tool_result blocks — not rendered directly
      } else if (msg.role === "assistant" && Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block.type === "text" && block.text) {
            chatMessages.push({
              id: crypto.randomUUID(),
              type: "agent_thought",
              text: block.text,
              timestamp: i,
            });
          }
          // Emit survey bubble when we see the dispatch tool_use
          if (block.type === "tool_use" && dispatchTools.has(block.name)) {
            // Find the order_id from the next message's tool_result
            const nextMsg = data.messages[i + 1];
            if (!nextMsg || !Array.isArray(nextMsg.content)) continue;
            for (const rb of nextMsg.content) {
              if (rb.type !== "tool_result" || rb.tool_use_id !== block.id) continue;
              const orderId = typeof rb.content === "string" ? rb.content.trim() : "";
              if (!orderId || emittedOrders.has(orderId)) continue;
              emittedOrders.add(orderId);
              const order = orderById.get(orderId) ?? {
                order_id: orderId,
                tool: block.name,
                question: (block.input as Record<string, unknown>).question as string ?? "",
                status: "complete",
                is_complete: true,
                distribution: null,
                winner: null,
                n_responses: null,
                country_counts: {},
              };
              const surveyMsg: SurveyResult = {
                id: crypto.randomUUID(),
                type: "survey_result",
                order,
                chartCapture: null, // SurveyResultCard re-captures on render
                timestamp: i,
              };
              chatMessages.push(surveyMsg);
            }
          }
        }
      }
    }

    // ── Restore brief and sections ─────────────────────────────────────────────
    const restoredBrief = data.brief ?? null;
    const restoredSections = restoredBrief?.sections ?? [];

    // Populate orders Map for the store
    const ordersMap = new Map<string, OrderState>();
    for (const [id, order] of orderById) {
      ordersMap.set(id, order);
    }

    get()._abortController?.abort();

    set({
      sessionId,
      conversationHistory: data.messages,
      chatMessages,
      isDone: true,
      isStreaming: false,
      error: null,
      currentQuestion: restoredBrief?.question ?? data.title ?? "",
      orders: ordersMap,
      chartCaptures: new Map(),
      sections: restoredSections,
      brief: restoredBrief,
      isPdfPanelOpen: false,
      isArtifactsOpen: false,
      _abortController: null,
    });
  },

  // ─── startResearch ──────────────────────────────────────────────────────────

  startResearch: (question, targeting) => {
    get()._abortController?.abort();
    const controller = new AbortController();
    const sessionId = crypto.randomUUID();

    const userMsg: UserMessage = {
      id: crypto.randomUUID(),
      type: "user_message",
      text: question,
      timestamp: Date.now(),
    };

    // Snapshot persisted state before the set() call
    const { conversationHistory, chatMessages: prevMessages, authToken, currentTargeting } = get();
    const effectiveTargeting = targeting ?? currentTargeting;

    set({
      _abortController: controller,
      sessionId,
      isStreaming: true,
      isDone: false,
      error: null,
      currentQuestion: question,
      // Append to existing chat history so the user can scroll back through prior sessions
      chatMessages: [...prevMessages, userMsg],
      orders: new Map(),
      chartCaptures: new Map(),
      sections: [],
      brief: null,
      isPdfPanelOpen: false,
      conversationHistory,
      currentTargeting: emptyTargeting(),
    });

    const extraHeaders: Record<string, string> = authToken ? { Authorization: `Bearer ${authToken}` } : {};

    streamSSE(
      "http://localhost:8000/research/stream",
      { question, session_id: sessionId, messages: conversationHistory, targeting: effectiveTargeting },
      controller.signal,
      extraHeaders,
      (evt) => get()._applySSEEvent(evt),
      (msg) => set({ isStreaming: false, error: msg }),
      () => set((s) => ({ isStreaming: s.isDone ? false : false })),
    ).then(() => {
      set((s) => ({ isStreaming: s.isDone ? false : s.isStreaming && false }));
    });
  },

  // ─── setTargeting ────────────────────────────────────────────────────────────

  setTargeting: (targeting) => set({ currentTargeting: targeting }),

  // ─── compileFindings ────────────────────────────────────────────────────────

  compileFindings: () => {
    const { conversationHistory, sessionId, authToken } = get();
    if (conversationHistory.length === 0) return;

    get()._abortController?.abort();
    const controller = new AbortController();

    set({
      _abortController: controller,
      isStreaming: true,
      isDone: false,
      error: null,
      sections: [],
      brief: null,
    });

    const extraHeaders: Record<string, string> = authToken ? { Authorization: `Bearer ${authToken}` } : {};

    streamSSE(
      "http://localhost:8000/research/compile",
      { session_id: sessionId ?? crypto.randomUUID(), messages: conversationHistory },
      controller.signal,
      extraHeaders,
      (evt) => get()._applySSEEvent(evt),
      (msg) => set({ isStreaming: false, error: msg }),
      () => {},
    ).then(() => {
      set((s) => ({ isStreaming: s.isDone ? false : s.isStreaming && false }));
    });
  },

  // ─── stopResearch ───────────────────────────────────────────────────────────

  stopResearch: () => {
    get()._abortController?.abort();
    set({ isStreaming: false });
  },

  // ─── submitAnswer ───────────────────────────────────────────────────────────

  submitAnswer: (questionIndex, answer) => {
    const { sessionId, authToken } = get();
    if (!sessionId) return;

    set((s) => ({
      chatMessages: s.chatMessages.map((m) =>
        m.type === "clarifying_question" &&
        m.questionIndex === questionIndex &&
        m.answeredWith === null
          ? { ...m, answeredWith: answer }
          : m,
      ),
    }));

    const extraHeaders: Record<string, string> = authToken ? { Authorization: `Bearer ${authToken}` } : {};

    fetch("http://localhost:8000/research/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...extraHeaders },
      body: JSON.stringify({ session_id: sessionId, question_index: questionIndex, answer }),
    });
  },

  // ─── setChartCapture ────────────────────────────────────────────────────────

  setChartCapture: (orderId, dataUrl) => {
    set((s) => {
      const chartCaptures = new Map(s.chartCaptures);
      chartCaptures.set(orderId, dataUrl);
      const chatMessages = s.chatMessages.map((m) =>
        m.type === "survey_result" && m.order.order_id === orderId && m.chartCapture === null
          ? { ...m, chartCapture: dataUrl }
          : m,
      );
      return { chartCaptures, chatMessages };
    });
  },

  openPdfPanel: () => set({ isPdfPanelOpen: true }),
  closePdfPanel: () => set({ isPdfPanelOpen: false }),
  deleteSession: async (sessionId) => {
    const { authToken } = get();
    if (!authToken) return;
    await fetch(`http://localhost:8000/sessions/${sessionId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${authToken}` },
    });
    set((s) => ({ sessionHistory: s.sessionHistory.filter((h) => h.id !== sessionId) }));
    // If the deleted session is currently loaded, reset the chat
    if (get().sessionId === sessionId) {
      get().reset();
    }
  },

  renameSession: async (sessionId, title) => {
    const { authToken } = get();
    if (!authToken) return;
    await fetch(`http://localhost:8000/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
      body: JSON.stringify({ title }),
    });
    set((s) => ({
      sessionHistory: s.sessionHistory.map((h) =>
        h.id === sessionId ? { ...h, title } : h,
      ),
    }));
  },

  openArtifacts: () => set({ isArtifactsOpen: true }),
  closeArtifacts: () => set({ isArtifactsOpen: false }),

  reset: () =>
    set((s) => ({
      ...INITIAL_STATE,
      conversationHistory: [],
      currentTargeting: emptyTargeting(),
      // Preserve auth and session history across resets
      authToken: s.authToken,
      sessionHistory: s.sessionHistory,
      isLoadingSessions: false,
      isArtifactsOpen: false,
    })),

  // ─── _applySSEEvent ─────────────────────────────────────────────────────────

  _applySSEEvent: (evt) => {
    if (evt.event === "targeting_update") {
      set({
        currentTargeting: {
          country_codes: evt.country_codes,
          languages: evt.languages,
          age_groups: evt.age_groups,
          genders: evt.genders,
        },
      });
      return;
    }

    if (evt.event === "clarifying_question") {
      const msg: ClarifyingQuestion = {
        id: crypto.randomUUID(),
        type: "clarifying_question",
        sessionId: evt.session_id,
        questionIndex: evt.question_index,
        question: evt.question,
        options: evt.options,
        answeredWith: null,
        timestamp: Date.now(),
      };
      set((s) => ({ chatMessages: [...s.chatMessages, msg] }));
      return;
    }

    if (evt.event === "agent_thought") {
      const msg: AgentThought = {
        id: crypto.randomUUID(),
        type: "agent_thought",
        text: evt.text,
        timestamp: Date.now(),
      };
      set((s) => ({ chatMessages: [...s.chatMessages, msg] }));
      return;
    }

    if (evt.event === "order_dispatched") {
      const orderState: OrderState = {
        order_id: evt.order_id,
        tool: evt.tool,
        question: evt.question,
        status: "dispatched",
        is_complete: false,
        distribution: null,
        winner: null,
        n_responses: null,
        country_counts: {},
      };
      const msg: SurveyResult = {
        id: crypto.randomUUID(),
        type: "survey_result",
        order: orderState,
        chartCapture: null,
        timestamp: Date.now(),
      };
      set((s) => {
        const orders = new Map(s.orders);
        orders.set(evt.order_id, orderState);
        return { orders, chatMessages: [...s.chatMessages, msg] };
      });
      return;
    }

    if (evt.event === "order_progress") {
      set((s) => {
        const existing = s.orders.get(evt.order_id);
        if (!existing) return s;
        const updated: OrderState = { ...existing, status: evt.status, is_complete: evt.is_complete };
        const orders = new Map(s.orders);
        orders.set(evt.order_id, updated);
        const chatMessages = s.chatMessages.map((m) =>
          m.type === "survey_result" && m.order.order_id === evt.order_id
            ? { ...m, order: updated }
            : m,
        );
        return { orders, chatMessages };
      });
      return;
    }

    if (evt.event === "order_partial_results") {
      set((s) => {
        const existing = s.orders.get(evt.order_id);
        if (!existing) return s;
        const updated: OrderState = {
          ...existing,
          distribution: evt.distribution,
          winner: evt.winner,
          n_responses: evt.n_responses,
          country_counts: evt.country_counts ?? {},
          // is_complete stays false — order is still collecting
        };
        const orders = new Map(s.orders);
        orders.set(evt.order_id, updated);
        const chatMessages = s.chatMessages.map((m) =>
          m.type === "survey_result" && m.order.order_id === evt.order_id
            ? { ...m, order: updated }
            : m,
        );
        return { orders, chatMessages };
      });
      return;
    }

    if (evt.event === "order_complete") {
      set((s) => {
        const existing = s.orders.get(evt.order_id);
        const updated: OrderState = {
          ...(existing ?? {
            order_id: evt.order_id,
            tool: "unknown",
            question: "",
            status: "complete",
            country_counts: {},
          }),
          is_complete: true,
          distribution: evt.distribution,
          winner: evt.winner,
          n_responses: evt.n_responses,
          country_counts: evt.country_counts ?? {},
        };
        const orders = new Map(s.orders);
        orders.set(evt.order_id, updated);
        const chatMessages = s.chatMessages.map((m) =>
          m.type === "survey_result" && m.order.order_id === evt.order_id
            ? { ...m, order: updated }
            : m,
        );
        return { orders, chatMessages };
      });
      return;
    }

    if (evt.event === "brief_update") {
      set((s) => ({
        sections: [...s.sections, evt.section],
        isPdfPanelOpen: true,
      }));
      return;
    }

    if (evt.event === "done") {
      set((s) => ({
        isDone: true,
        isStreaming: false,
        brief: evt.brief,
        // Update conversation history only when messages are provided (research stream, not compile)
        conversationHistory:
          evt.messages && evt.messages.length > 0
            ? (evt.messages as AnthropicMessage[])
            : s.conversationHistory,
      }));
      // Refresh sidebar session list after new session is saved
      get().fetchSessions();
    }
  },
}));
