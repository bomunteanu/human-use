import { useState } from "react";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInputBar } from "./ChatInputBar";
import { useResearchContext } from "../context/ResearchContext";

export function ChatPane() {
  const { state, startResearch, stopResearch, dispatch } = useResearchContext();
  const [inputText, setInputText] = useState("");
  const [countryCodes, setCountryCodes] = useState<string[]>([]);

  const handleSubmit = () => {
    const q = inputText.trim();
    if (!q || state.isStreaming) return;
    startResearch(q, countryCodes);
    setInputText("");
  };

  const handleCompileFindings = () => {
    // Abort the stream so the agent stops dispatching more surveys,
    // then open the PDF panel so the user sees whatever brief content exists.
    stopResearch();
    dispatch({ type: "OPEN_PDF_PANEL" });
  };

  const hasOrders = state.orders.size > 0;
  const hasSections = state.sections.length > 0;

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
        <ChatMessageList messages={state.messages} />
      )}

      {/* Input bar */}
      <ChatInputBar
        value={inputText}
        onChange={setInputText}
        countryCodes={countryCodes}
        onCountryCodesChange={setCountryCodes}
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
