import { useEffect } from "react";
import { PenLine, Clock, Search, LogOut, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useResearchContext } from "../context/ResearchContext";
import { useStore } from "../store";
import { useAuth } from "../hooks/useAuth";

export function Sidebar() {
  const { dispatch } = useResearchContext();
  const fetchSessions = useStore((s) => s.fetchSessions);
  const loadSession = useStore((s) => s.loadSession);
  const sessionHistory = useStore((s) => s.sessionHistory);
  const isLoadingSessions = useStore((s) => s.isLoadingSessions);
  const currentSessionId = useStore((s) => s.sessionId);
  const openArtifacts = useStore((s) => s.openArtifacts);
  const completedCount = sessionHistory.filter((s) => s.brief !== null).length;
  const { logout } = useAuth();

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleNewResearch = () => {
    dispatch({ type: "RESET" });
  };

  return (
    <div className="w-60 flex-shrink-0 flex flex-col h-full bg-[#161b22] border-r border-[#21262d]">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-[#21262d] flex items-center justify-between">
        <span className="text-[15px] font-semibold text-[#e6edf3]">human-use</span>
        <button
          onClick={logout}
          title="Sign out"
          className="text-[#7d8590] hover:text-[#e6edf3] transition-colors"
        >
          <LogOut size={14} />
        </button>
      </div>

      {/* New Research button */}
      <div className="px-3 py-3 space-y-1.5">
        <Button
          onClick={handleNewResearch}
          className="w-full h-9 text-[13px] bg-[#21262d] hover:bg-[#30363d] text-[#e6edf3] border border-[#30363d] rounded-[8px] gap-2 justify-start"
        >
          <PenLine size={14} />
          New Research
        </Button>

        {/* Reports / Artifacts button */}
        <button
          onClick={openArtifacts}
          className="w-full h-9 flex items-center gap-2 px-3 text-[13px] text-[#7d8590] hover:text-[#e6edf3] hover:bg-[#21262d] rounded-[8px] transition-colors"
        >
          <FileText size={14} />
          <span>Reports</span>
          {completedCount > 0 && (
            <span className="ml-auto text-[11px] bg-[#21262d] text-[#58a6ff] rounded-full px-1.5 py-0.5 leading-none">
              {completedCount}
            </span>
          )}
        </button>
      </div>

      {/* History section */}
      <div className="flex-1 overflow-y-auto px-3 space-y-0.5">
        <div className="flex items-center gap-1.5 px-2 py-1.5 mb-1">
          <Clock size={11} className="text-[#7d8590]" />
          <span className="text-[11px] font-medium text-[#7d8590] uppercase tracking-wide">
            History
          </span>
        </div>

        {isLoadingSessions && sessionHistory.length === 0 && (
          <div className="space-y-1.5 px-2 py-1">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 bg-[#21262d] rounded-[6px] animate-pulse" />
            ))}
          </div>
        )}

        {!isLoadingSessions && sessionHistory.length === 0 && (
          <p className="px-2 py-2 text-[11px] text-[#7d8590]">No sessions yet</p>
        )}

        {sessionHistory.map((item) => (
          <button
            key={item.id}
            onClick={() => loadSession(item.id)}
            className={`w-full text-left px-2 py-2 rounded-[6px] group hover:bg-[#21262d] transition-colors ${
              currentSessionId === item.id ? "bg-[#21262d]" : ""
            }`}
          >
            <div className="flex items-start gap-2">
              <Search size={12} className="text-[#7d8590] mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-[12px] text-[#e6edf3] leading-snug truncate">
                  {item.title}
                </p>
                <p className="text-[11px] text-[#7d8590] mt-0.5">
                  {new Date(item.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </p>
              </div>
              {item.brief && (
                <FileText size={10} className="text-[#58a6ff] mt-1 flex-shrink-0" />
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
