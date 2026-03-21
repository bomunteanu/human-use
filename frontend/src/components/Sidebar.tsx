import { PenLine, Clock, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useResearchContext } from "../context/ResearchContext";

// Static placeholder history items — no backend connection
const PLACEHOLDER_HISTORY = [
  { id: "1", title: "Consumer attitudes toward AI assistants", date: "Mar 18" },
  { id: "2", title: "Preferred social media formats for Gen Z", date: "Mar 15" },
  { id: "3", title: "Brand trust in subscription services", date: "Mar 12" },
  { id: "4", title: "Remote work productivity perceptions", date: "Mar 8" },
];

export function Sidebar() {
  const { dispatch } = useResearchContext();

  const handleNewResearch = () => {
    dispatch({ type: "RESET" });
  };

  return (
    <div className="w-60 flex-shrink-0 flex flex-col h-full bg-[#161b22] border-r border-[#21262d]">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-[#21262d]">
        <span className="text-[15px] font-semibold text-[#e6edf3]">human-use</span>
      </div>

      {/* New Research button */}
      <div className="px-3 py-3">
        <Button
          onClick={handleNewResearch}
          className="w-full h-9 text-[13px] bg-[#21262d] hover:bg-[#30363d] text-[#e6edf3] border border-[#30363d] rounded-[8px] gap-2 justify-start"
        >
          <PenLine size={14} />
          New Research
        </Button>
      </div>

      {/* History section */}
      <div className="flex-1 overflow-y-auto px-3 space-y-0.5">
        <div className="flex items-center gap-1.5 px-2 py-1.5 mb-1">
          <Clock size={11} className="text-[#7d8590]" />
          <span className="text-[11px] font-medium text-[#7d8590] uppercase tracking-wide">
            History
          </span>
          <span className="text-[10px] text-[#7d8590]/50 ml-auto">coming soon</span>
        </div>

        {PLACEHOLDER_HISTORY.map((item) => (
          <button
            key={item.id}
            disabled
            className="w-full text-left px-2 py-2 rounded-[6px] opacity-40 cursor-not-allowed group"
          >
            <div className="flex items-start gap-2">
              <Search size={12} className="text-[#7d8590] mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-[12px] text-[#e6edf3] leading-snug truncate">
                  {item.title}
                </p>
                <p className="text-[11px] text-[#7d8590] mt-0.5">{item.date}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
