import { useCallback, useRef, useState } from "react";
import type { AgentThoughtEvent, BriefSection, OrderState, SSEEvent } from "../types";

interface StreamState {
  thoughts: AgentThoughtEvent[];
  orders: Map<string, OrderState>;
  sections: BriefSection[];
  isDone: boolean;
  isStreaming: boolean;
  error: string | null;
}

function applyEvent(prev: StreamState, evt: SSEEvent): StreamState {
  const next = { ...prev };

  if (evt.event === "agent_thought") {
    next.thoughts = [...prev.thoughts, evt];
  } else if (evt.event === "order_dispatched") {
    const orders = new Map(prev.orders);
    orders.set(evt.order_id, {
      order_id: evt.order_id,
      tool: evt.tool,
      question: evt.question,
      status: "dispatched",
      is_complete: false,
      distribution: null,
      winner: null,
      n_responses: null,
    });
    next.orders = orders;
  } else if (evt.event === "order_progress") {
    const orders = new Map(prev.orders);
    const existing = orders.get(evt.order_id);
    if (existing) {
      orders.set(evt.order_id, { ...existing, status: evt.status, is_complete: evt.is_complete });
    }
    next.orders = orders;
  } else if (evt.event === "order_complete") {
    const orders = new Map(prev.orders);
    const existing = orders.get(evt.order_id);
    if (existing) {
      orders.set(evt.order_id, {
        ...existing,
        is_complete: true,
        distribution: evt.distribution,
        winner: evt.winner,
        n_responses: evt.n_responses,
      });
    }
    next.orders = orders;
  } else if (evt.event === "brief_update") {
    next.sections = [...prev.sections, evt.section];
  } else if (evt.event === "done") {
    next.isDone = true;
    next.isStreaming = false;
  }

  return next;
}

// Parse a single SSE chunk (may contain multiple events separated by double newlines)
function* parseSSEChunk(chunk: string): Generator<SSEEvent> {
  // Normalize \r\n and \r to \n so splitting works regardless of server line endings
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

export function useResearchStream() {
  const [state, setState] = useState<StreamState>({
    thoughts: [],
    orders: new Map(),
    sections: [],
    isDone: false,
    isStreaming: false,
    error: null,
  });
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback((question: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({
      thoughts: [],
      orders: new Map(),
      sections: [],
      isDone: false,
      isStreaming: true,
      error: null,
    });

    (async () => {
      try {
        const res = await fetch("http://localhost:8000/research/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          setState((prev) => ({ ...prev, isStreaming: false, error: `HTTP ${res.status}` }));
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // Normalize line endings so boundary detection works
          buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

          // Process complete events (terminated by double newline)
          const boundary = buffer.lastIndexOf("\n\n");
          if (boundary === -1) continue;

          const complete = buffer.slice(0, boundary + 2);
          buffer = buffer.slice(boundary + 2);

          const events = [...parseSSEChunk(complete)];
          if (events.length > 0) {
            setState((prev) => events.reduce(applyEvent, prev));
          }
        }

        // Process any remaining buffer
        const remaining = [...parseSSEChunk(buffer)];
        if (remaining.length > 0) {
          setState((prev) => remaining.reduce(applyEvent, prev));
        }

        setState((prev) => ({ ...prev, isStreaming: false }));
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setState((prev) => ({ ...prev, isStreaming: false, error: "Connection lost." }));
      }
    })();
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => ({ ...prev, isStreaming: false }));
  }, []);

  return { state, start, stop };
}
