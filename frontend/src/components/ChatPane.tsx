import { ChatMessageList } from "./ChatMessageList";
import { ChatInputBar } from "./ChatInputBar";
import { useResearchContext } from "../context/ResearchContext";
import { useStore } from "../store";
import { useState } from "react";

export function ChatPane() {
  const { state, startResearch, stopResearch, compileFindings, dispatch } = useResearchContext();
  const { currentTargeting, setTargeting } = useStore();
  const [inputText, setInputText] = useState("");

  const handleSubmit = () => {
    const q = inputText.trim();
    if (!q || state.isStreaming) return;
    startResearch(q, currentTargeting);
    setInputText("");
  };

  const handleCompileFindings = () => {
    if (state.isDone && state.sections.length > 0) {
      // Research finished — just reopen the PDF panel
      dispatch({ type: "OPEN_PDF_PANEL" });
      return;
    }
    // Stream is running (or paused): stop it and synthesize what's collected
    stopResearch();
    compileFindings();
  };

  const hasOrders = state.orders.size > 0;
  const hasSections = state.sections.length > 0;

  // Show a thinking bubble while the LLM is synthesising results into a brief
  // (all surveys complete, no brief sections emitted yet, stream still active).
  const showThinking =
    state.isStreaming &&
    state.orders.size > 0 &&
    [...state.orders.values()].every((o) => o.is_complete) &&
    !hasSections;

  return (
    <div className="flex flex-col flex-1 min-w-0 h-full">
      {/* Error banner */}
      {state.error && (
        <div className="px-4 py-2 bg-red-900/20 border-b border-red-900/40">
          <span className="text-[12px] text-red-400">{state.error}</span>
        </div>
      )}

      {/* Streaming indicator */}
      {state.isStreaming && (
        <div className="px-4 py-1.5 border-b border-[#21262d]">
          <span className="text-[11px] text-[#2f81f7] animate-pulse">
            {state.messages.some(
              (m) => m.type === "clarifying_question" && m.answeredWith === null,
            )
              ? "Waiting for your answer..."
              : "Researching..."}
          </span>
        </div>
      )}

      {/* Message list — empty state */}
      {state.messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 px-8">
          <div className="text-center space-y-1">
            <p className="text-[20px] font-semibold text-[#e6edf3]">What do you want to research?</p>
            <p className="text-[13px] text-[#7d8590]">
              Ask a question and the agent will survey real people for you.
            </p>
          </div>
        </div>
      ) : (
        <ChatMessageList messages={state.messages} showThinking={showThinking} />
      )}

      {/* Input bar */}
      <ChatInputBar
        value={inputText}
        onChange={setInputText}
        targeting={currentTargeting}
        onTargetingChange={setTargeting}
        onSubmit={handleSubmit}
        onStop={stopResearch}
        onCompileFindings={handleCompileFindings}
        isStreaming={state.isStreaming}
        hasOrders={hasOrders}
        hasSections={hasSections}
        disabled={false}
      />
    </div>
  );
}
