/**
 * Thin compatibility shim over the Zustand store.
 * All components continue to call useResearchContext() and get the same API they expect.
 * State lives in the Zustand store (store.ts), not here.
 */
import type { ReactNode } from "react";
import { useStore, type ResearchStore } from "../store";
import type { BriefSection, ChatMessage, OrderState, ResearchBrief } from "../types";

// ─── Legacy state shape (kept for component compatibility) ────────────────────

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

// ─── Legacy action type (kept for components that call dispatch directly) ─────

export type ResearchAction =
  | { type: "OPEN_PDF_PANEL" }
  | { type: "CLOSE_PDF_PANEL" }
  | { type: "RESET" };

interface ResearchContextValue {
  state: ResearchState;
  dispatch: (action: ResearchAction) => void;
  startResearch: ResearchStore["startResearch"];
  stopResearch: ResearchStore["stopResearch"];
  submitAnswer: ResearchStore["submitAnswer"];
  setChartCapture: ResearchStore["setChartCapture"];
  compileFindings: ResearchStore["compileFindings"];
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useResearchContext(): ResearchContextValue {
  const store = useStore();

  const state: ResearchState = {
    sessionId: store.sessionId,
    isStreaming: store.isStreaming,
    isDone: store.isDone,
    error: store.error,
    currentQuestion: store.currentQuestion,
    messages: store.chatMessages,
    orders: store.orders,
    chartCaptures: store.chartCaptures,
    sections: store.sections,
    brief: store.brief,
    isPdfPanelOpen: store.isPdfPanelOpen,
  };

  const dispatch = (action: ResearchAction) => {
    switch (action.type) {
      case "OPEN_PDF_PANEL":
        store.openPdfPanel();
        break;
      case "CLOSE_PDF_PANEL":
        store.closePdfPanel();
        break;
      case "RESET":
        store.reset();
        break;
    }
  };

  return {
    state,
    dispatch,
    startResearch: store.startResearch,
    stopResearch: store.stopResearch,
    submitAnswer: store.submitAnswer,
    setChartCapture: store.setChartCapture,
    compileFindings: store.compileFindings,
  };
}

// ─── Provider (no-op shell — state is global in Zustand) ─────────────────────

export function ResearchProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
