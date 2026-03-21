import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ThoughtStream } from "./components/ThoughtStream";
import { OrdersPanel } from "./components/OrdersPanel";
import { BriefPanel } from "./components/BriefPanel";
import { useResearchStream } from "./hooks/useResearchStream";

export default function App() {
  const [question, setQuestion] = useState("");
  const { state, start, stop } = useResearchStream();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim()) {
      start(question.trim());
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#0d1117] p-4 gap-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="text-[15px] font-semibold text-[#e6edf3]">human-use</span>
        <span className="text-[#21262d]">|</span>
        <form onSubmit={handleSubmit} className="flex gap-2 flex-1 max-w-2xl">
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Enter a research question..."
            disabled={state.isStreaming}
            className="flex-1 bg-[#0d1117] border-[#21262d] text-[#e6edf3] placeholder:text-[#7d8590] focus-visible:ring-[#2f81f7] text-[13px] h-8"
          />
          {state.isStreaming ? (
            <Button
              type="button"
              onClick={stop}
              className="h-8 px-4 text-[13px] bg-[#21262d] hover:bg-[#30363d] text-[#e6edf3] border-0 rounded-[6px]"
            >
              Stop
            </Button>
          ) : (
            <Button
              type="submit"
              disabled={!question.trim()}
              className="h-8 px-4 text-[13px] bg-[#2f81f7] hover:bg-[#388bfd] text-white border-0 rounded-[6px] disabled:opacity-40"
            >
              Research
            </Button>
          )}
        </form>
        {state.error && (
          <span className="text-[12px] text-red-400">{state.error}</span>
        )}
        {state.isStreaming && (
          <span className="text-[12px] text-[#2f81f7] animate-pulse">Streaming...</span>
        )}
      </div>

      {/* Three panels */}
      <div className="flex flex-1 gap-4 min-h-0">
        <div className="flex-1 min-h-0">
          <ThoughtStream thoughts={state.thoughts} />
        </div>
        <div className="flex-1 min-h-0">
          <OrdersPanel orders={state.orders} />
        </div>
        <div className="flex-1 min-h-0">
          <BriefPanel sections={state.sections} isDone={state.isDone} />
        </div>
      </div>
    </div>
  );
}
