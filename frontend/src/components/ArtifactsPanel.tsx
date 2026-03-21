import type { ReactElement } from "react";
import { X, FileText, Download, ExternalLink } from "lucide-react";
import { PDFDownloadLink, type DocumentProps } from "@react-pdf/renderer";
import { useStore } from "../store";
import { ResearchPdfDocument } from "./ResearchPdfDocument";
import type { SessionSummary } from "../types";

function ArtifactRow({ item }: { item: SessionSummary }) {
  const loadSession = useStore((s) => s.loadSession);
  const openPdfPanel = useStore((s) => s.openPdfPanel);
  const closeArtifacts = useStore((s) => s.closeArtifacts);

  if (!item.brief) return null;

  const pdfTitle = item.brief.title || item.title;
  const filename = `${pdfTitle.slice(0, 40).replace(/\s+/g, "_")}_brief.pdf`;

  const doc = (
    <ResearchPdfDocument
      title={pdfTitle}
      sections={item.brief.sections}
      completedOrders={[]}
      svgCaptures={new Map()}
    />
  ) as ReactElement<DocumentProps>;

  const handleOpen = async () => {
    await loadSession(item.id);
    openPdfPanel();
    closeArtifacts();
  };

  return (
    <div className="flex items-start gap-3 px-3 py-3 rounded-[8px] hover:bg-[#21262d] transition-colors group">
      <div className="mt-0.5 flex-shrink-0 w-8 h-8 rounded-[6px] bg-[#21262d] group-hover:bg-[#30363d] flex items-center justify-center">
        <FileText size={14} className="text-[#58a6ff]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[12px] font-medium text-[#e6edf3] leading-snug truncate">
          {pdfTitle}
        </p>
        <p className="text-[11px] text-[#7d8590] mt-0.5">
          {new Date(item.created_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
        {item.brief.summary && (
          <p className="text-[11px] text-[#7d8590] mt-1 line-clamp-2 leading-relaxed">
            {item.brief.summary}
          </p>
        )}
      </div>
      <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={handleOpen}
          title="Open report"
          className="h-7 w-7 flex items-center justify-center rounded-[6px] hover:bg-[#30363d] text-[#7d8590] hover:text-[#e6edf3] transition-colors"
        >
          <ExternalLink size={12} />
        </button>
        <PDFDownloadLink document={doc} fileName={filename}>
          {({ loading }) => (
            <button
              disabled={loading}
              title="Download PDF"
              className="h-7 w-7 flex items-center justify-center rounded-[6px] hover:bg-[#30363d] text-[#7d8590] hover:text-[#e6edf3] transition-colors disabled:opacity-40"
            >
              <Download size={12} />
            </button>
          )}
        </PDFDownloadLink>
      </div>
    </div>
  );
}

export function ArtifactsPanel() {
  const closeArtifacts = useStore((s) => s.closeArtifacts);
  const sessionHistory = useStore((s) => s.sessionHistory);

  const completed = sessionHistory.filter((s) => s.brief !== null);

  return (
    <div className="flex flex-col h-full bg-[#161b22]">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#21262d]">
        <FileText size={14} className="text-[#58a6ff]" />
        <span className="text-[13px] font-semibold text-[#e6edf3] flex-1">Reports</span>
        <button
          onClick={closeArtifacts}
          className="h-7 w-7 flex items-center justify-center rounded-[6px] hover:bg-[#21262d] text-[#7d8590] hover:text-[#e6edf3] transition-colors"
          title="Close"
        >
          <X size={14} />
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {completed.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 gap-2">
            <FileText size={24} className="text-[#30363d]" />
            <p className="text-[12px] text-[#7d8590]">No reports yet</p>
            <p className="text-[11px] text-[#7d8590]/60 text-center px-6">
              Complete a research session to generate a report
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {completed.map((item) => (
              <ArtifactRow key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
