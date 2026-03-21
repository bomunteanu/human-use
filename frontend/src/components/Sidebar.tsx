import { useEffect, useRef, useState } from "react";
import { PenLine, Clock, Search, LogOut, FileText, Trash2, Pencil, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useResearchContext } from "../context/ResearchContext";
import { useStore } from "../store";
import { useAuth } from "../hooks/useAuth";

export function Sidebar() {
  const { dispatch } = useResearchContext();
  const fetchSessions = useStore((s) => s.fetchSessions);
  const loadSession = useStore((s) => s.loadSession);
  const deleteSession = useStore((s) => s.deleteSession);
  const renameSession = useStore((s) => s.renameSession);
  const sessionHistory = useStore((s) => s.sessionHistory);
  const isLoadingSessions = useStore((s) => s.isLoadingSessions);
  const currentSessionId = useStore((s) => s.sessionId);
  const openArtifacts = useStore((s) => s.openArtifacts);
  const completedCount = sessionHistory.filter((s) => s.brief !== null).length;
  const { logout } = useAuth();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const editInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  useEffect(() => {
    if (editingId) editInputRef.current?.focus();
  }, [editingId]);

  const handleNewResearch = () => {
    dispatch({ type: "RESET" });
  };

  const startRename = (e: React.MouseEvent, id: string, title: string) => {
    e.stopPropagation();
    setEditingId(id);
    setEditingTitle(title);
  };

  const commitRename = async () => {
    if (!editingId || !editingTitle.trim()) { setEditingId(null); return; }
    await renameSession(editingId, editingTitle.trim());
    setEditingId(null);
  };

  const cancelRename = () => setEditingId(null);

  const handleRenameKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") commitRename();
    if (e.key === "Escape") cancelRename();
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
          <div
            key={item.id}
            className={`group relative w-full rounded-[6px] transition-colors ${
              currentSessionId === item.id ? "bg-[#21262d]" : "hover:bg-[#21262d]"
            }`}
          >
            {editingId === item.id ? (
              /* ── Inline rename mode ── */
              <div className="flex items-center gap-1 px-2 py-2">
                <Search size={12} className="text-[#7d8590] flex-shrink-0" />
                <input
                  ref={editInputRef}
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onKeyDown={handleRenameKey}
                  onBlur={commitRename}
                  className="flex-1 min-w-0 bg-[#0d1117] border border-[#58a6ff] rounded px-1.5 py-0.5 text-[12px] text-[#e6edf3] outline-none"
                />
                <button
                  onMouseDown={(e) => { e.preventDefault(); commitRename(); }}
                  className="text-[#3fb950] hover:text-[#56d364] flex-shrink-0"
                >
                  <Check size={12} />
                </button>
                <button
                  onMouseDown={(e) => { e.preventDefault(); cancelRename(); }}
                  className="text-[#7d8590] hover:text-[#e6edf3] flex-shrink-0"
                >
                  <X size={12} />
                </button>
              </div>
            ) : (
              /* ── Normal row ── */
              <button
                onClick={() => loadSession(item.id)}
                className="w-full text-left px-2 py-2"
              >
                <div className="flex items-start gap-2">
                  <Search size={12} className="text-[#7d8590] mt-0.5 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] text-[#e6edf3] leading-snug truncate pr-10">
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
            )}

            {/* Action buttons — visible on hover when not editing */}
            {editingId !== item.id && (
              <div className="absolute right-1.5 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-0.5">
                <button
                  onClick={(e) => startRename(e, item.id, item.title)}
                  title="Rename"
                  className="p-1 text-[#7d8590] hover:text-[#e6edf3] hover:bg-[#30363d] rounded transition-colors"
                >
                  <Pencil size={11} />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteSession(item.id); }}
                  title="Delete"
                  className="p-1 text-[#7d8590] hover:text-[#f85149] hover:bg-[#30363d] rounded transition-colors"
                >
                  <Trash2 size={11} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
