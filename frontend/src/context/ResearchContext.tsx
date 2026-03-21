import {
  createContext,
  useCallback,
  useContext,
  useReducer,
  useRef,
  type ReactNode,
} from "react";
import type {
  AgentThought,
  BriefSection,
  ClarifyingQuestion,
  ChatMessage,
  OrderState,
  ResearchBrief,
  SSEEvent,
  SurveyResult,
  UserMessage,
} from "../types";

// ─── State ────────────────────────────────────────────────────────────────────

export interface ResearchState {
  sessionId: string | null;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
  currentQuestion: string;

  messages: ChatMessage[];
  orders: Map<string, OrderState>;
  chartCaptures: Map<string, string>;

  sections: BriefSection[];
  brief: ResearchBrief | null;

  isPdfPanelOpen: boolean;
}

const INITIAL_STATE: ResearchState = {
  sessionId: null,
  isStreaming: false,
  isDone: false,
  error: null,
  currentQuestion: "",
  messages: [],
  orders: new Map(),
  chartCaptures: new Map(),
  sections: [],
  brief: null,
  isPdfPanelOpen: false,
};

// ─── Actions ──────────────────────────────────────────────────────────────────

export type ResearchAction =
  | { type: "START"; question: string; sessionId: string }
  | { type: "STOP" }
  | { type: "SSE_EVENT"; event: SSEEvent }
  | { type: "SUBMIT_ANSWER"; questionIndex: number; answer: string }
  | { type: "SET_CHART_CAPTURE"; orderId: string; dataUrl: string }
  | { type: "SET_ERROR"; error: string }
  | { type: "OPEN_PDF_PANEL" }
  | { type: "CLOSE_PDF_PANEL" }
  | { type: "RESET" };

// ─── Reducer ──────────────────────────────────────────────────────────────────

function applySSEEvent(state: ResearchState, evt: SSEEvent): ResearchState {
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
    return { ...state, messages: [...state.messages, msg] };
  }

  if (evt.event === "agent_thought") {
    const msg: AgentThought = {
      id: crypto.randomUUID(),
      type: "agent_thought",
      text: evt.text,
      timestamp: Date.now(),
    };
    return { ...state, messages: [...state.messages, msg] };
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
    };
    const orders = new Map(state.orders);
    orders.set(evt.order_id, orderState);
    // Push the bubble immediately so the user sees it arrive
    const msg: SurveyResult = {
      id: crypto.randomUUID(),
      type: "survey_result",
      order: orderState,
      chartCapture: null,
      timestamp: Date.now(),
    };
    return { ...state, orders, messages: [...state.messages, msg] };
  }

  if (evt.event === "order_progress") {
    const orders = new Map(state.orders);
    const existing = orders.get(evt.order_id);
    if (!existing) return state;
    const updated: OrderState = { ...existing, status: evt.status, is_complete: evt.is_complete };
    orders.set(evt.order_id, updated);
    // Keep the SurveyResult message's order snapshot in sync
    const messages = state.messages.map((m) =>
      m.type === "survey_result" && m.order.order_id === evt.order_id
        ? { ...m, order: updated }
        : m,
    );
    return { ...state, orders, messages };
  }

  if (evt.event === "order_complete") {
    const orders = new Map(state.orders);
    const existing = orders.get(evt.order_id);
    const updated: OrderState = {
      ...(existing ?? {
        order_id: evt.order_id,
        tool: "unknown",
        question: "",
        status: "complete",
      }),
      is_complete: true,
      distribution: evt.distribution,
      winner: evt.winner,
      n_responses: evt.n_responses,
    };
    orders.set(evt.order_id, updated);
    // Update the existing bubble rather than adding a duplicate
    const messages = state.messages.map((m) =>
      m.type === "survey_result" && m.order.order_id === evt.order_id
        ? { ...m, order: updated }
        : m,
    );
    return { ...state, orders, messages };
  }

  if (evt.event === "brief_update") {
    return {
      ...state,
      sections: [...state.sections, evt.section],
      isPdfPanelOpen: true,
    };
  }

  if (evt.event === "done") {
    return {
      ...state,
      isDone: true,
      isStreaming: false,
      brief: evt.brief,
    };
  }

  return state;
}

function reducer(state: ResearchState, action: ResearchAction): ResearchState {
  switch (action.type) {
    case "START":
      return {
        ...INITIAL_STATE,
        sessionId: action.sessionId,
        isStreaming: true,
        currentQuestion: action.question,
        messages: [
          {
            id: crypto.randomUUID(),
            type: "user_message",
            text: action.question,
            timestamp: Date.now(),
          } satisfies UserMessage,
        ],
      };

    case "STOP":
      return { ...state, isStreaming: false };

    case "SSE_EVENT":
      return applySSEEvent(state, action.event);

    case "SUBMIT_ANSWER": {
      const messages = state.messages.map((m) => {
        if (
          m.type === "clarifying_question" &&
          m.questionIndex === action.questionIndex &&
          m.answeredWith === null
        ) {
          return { ...m, answeredWith: action.answer };
        }
        return m;
      });
      return { ...state, messages };
    }

    case "SET_CHART_CAPTURE": {
      const chartCaptures = new Map(state.chartCaptures);
      chartCaptures.set(action.orderId, action.dataUrl);
      const messages = state.messages.map((m) => {
        if (
          m.type === "survey_result" &&
          m.order.order_id === action.orderId &&
          m.chartCapture === null
        ) {
          return { ...m, chartCapture: action.dataUrl };
        }
        return m;
      });
      return { ...state, chartCaptures, messages };
    }

    case "SET_ERROR":
      return { ...state, isStreaming: false, error: action.error };

    case "OPEN_PDF_PANEL":
      return { ...state, isPdfPanelOpen: true };

    case "CLOSE_PDF_PANEL":
      return { ...state, isPdfPanelOpen: false };

    case "RESET":
      return INITIAL_STATE;

    default:
      return state;
  }
}

// ─── Context ──────────────────────────────────────────────────────────────────

interface ResearchContextValue {
  state: ResearchState;
  dispatch: React.Dispatch<ResearchAction>;
  startResearch: (question: string, countryCodes?: string[]) => void;
  stopResearch: () => void;
  submitAnswer: (questionIndex: number, answer: string) => void;
  setChartCapture: (orderId: string, dataUrl: string) => void;
}

const ResearchContext = createContext<ResearchContextValue | null>(null);

export function useResearchContext(): ResearchContextValue {
  const ctx = useContext(ResearchContext);
  if (!ctx) throw new Error("useResearchContext must be used within ResearchProvider");
  return ctx;
}

// ─── Provider ─────────────────────────────────────────────────────────────────

// The streaming logic lives here so it can call dispatch directly.
// Kept minimal — all state mutations go through the reducer.

// Parse a single SSE chunk (may contain multiple events separated by double newlines)
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

export function ResearchProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const startResearch = useCallback(
    (question: string, countryCodes: string[] = []) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const sessionId = crypto.randomUUID();
      sessionIdRef.current = sessionId;

      dispatch({ type: "START", question, sessionId });

      (async () => {
        try {
          const url = new URL("http://localhost:8000/research/stream");
          for (const code of countryCodes) {
            url.searchParams.append("country_codes", code);
          }
          const res = await fetch(url.toString(), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question, session_id: sessionId }),
            signal: controller.signal,
          });

          if (!res.ok || !res.body) {
            dispatch({ type: "SET_ERROR", error: `HTTP ${res.status}` });
            return;
          }

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

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
              dispatch({ type: "SSE_EVENT", event });
            }
          }

          const remaining = [...parseSSEChunk(buffer)];
          for (const event of remaining) {
            dispatch({ type: "SSE_EVENT", event });
          }

          dispatch({ type: "STOP" });
        } catch (err) {
          if ((err as Error).name === "AbortError") return;
          dispatch({ type: "SET_ERROR", error: "Connection lost." });
        }
      })();
    },
    [],
  );

  const stopResearch = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "STOP" });
  }, []);

  const submitAnswer = useCallback((questionIndex: number, answer: string) => {
    const sessionId = sessionIdRef.current;
    if (!sessionId) return;
    dispatch({ type: "SUBMIT_ANSWER", questionIndex, answer });
    fetch("http://localhost:8000/research/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        question_index: questionIndex,
        answer,
      }),
    });
  }, []);

  const setChartCapture = useCallback((orderId: string, dataUrl: string) => {
    dispatch({ type: "SET_CHART_CAPTURE", orderId, dataUrl });
  }, []);

  return (
    <ResearchContext.Provider
      value={{ state, dispatch, startResearch, stopResearch, submitAnswer, setChartCapture }}
    >
      {children}
    </ResearchContext.Provider>
  );
}
