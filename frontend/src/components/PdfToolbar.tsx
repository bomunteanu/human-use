import { X, ZoomIn, ZoomOut, RotateCcw, Download } from "lucide-react";
import { PDFDownloadLink, type DocumentProps } from "@react-pdf/renderer";
import { Button } from "@/components/ui/button";
import type { ReactElement } from "react";

interface Props {
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  onClose: () => void;
  isDone: boolean;
  filename: string;
  pdfDocument: ReactElement<DocumentProps>;
}

export function PdfToolbar({
  zoom,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  onClose,
  isDone,
  filename,
  pdfDocument,
}: Props) {
  return (
    <div className="flex items-center gap-1 px-3 py-2 border-b border-[#21262d] bg-[#161b22]">
      {/* Close */}
      <Button
        onClick={onClose}
        className="h-7 w-7 p-0 bg-transparent hover:bg-[#21262d] text-[#7d8590] hover:text-[#e6edf3] border-0 rounded-[6px]"
        title="Close PDF panel"
      >
        <X size={14} />
      </Button>

      <span className="text-[12px] font-medium text-[#e6edf3] flex-1 ml-1">
        Research Brief
      </span>

      {/* Zoom controls */}
      <div className="flex items-center gap-0.5">
        <Button
          onClick={onZoomOut}
          disabled={zoom <= 0.5}
          className="h-7 w-7 p-0 bg-transparent hover:bg-[#21262d] text-[#7d8590] hover:text-[#e6edf3] border-0 rounded-[6px] disabled:opacity-30"
          title="Zoom out"
        >
          <ZoomOut size={13} />
        </Button>

        <button
          onClick={onZoomReset}
          className="h-7 px-2 text-[11px] text-[#7d8590] hover:text-[#e6edf3] hover:bg-[#21262d] rounded-[6px] transition-colors min-w-[44px]"
          title="Reset zoom"
        >
          {Math.round(zoom * 100)}%
        </button>

        <Button
          onClick={onZoomIn}
          disabled={zoom >= 2.0}
          className="h-7 w-7 p-0 bg-transparent hover:bg-[#21262d] text-[#7d8590] hover:text-[#e6edf3] border-0 rounded-[6px] disabled:opacity-30"
          title="Zoom in"
        >
          <ZoomIn size={13} />
        </Button>
      </div>

      {/* Export */}
      {isDone ? (
        <PDFDownloadLink document={pdfDocument} fileName={filename}>
          {({ loading }) => (
            <Button
              disabled={loading}
              className="h-7 px-2.5 text-[12px] bg-[#21262d] hover:bg-[#30363d] text-[#e6edf3] border-0 rounded-[6px] gap-1.5 disabled:opacity-40"
            >
              <Download size={12} />
              {loading ? "Preparing..." : "Export"}
            </Button>
          )}
        </PDFDownloadLink>
      ) : (
        <Button
          disabled
          className="h-7 px-2.5 text-[12px] bg-[#21262d] text-[#7d8590] border-0 rounded-[6px] gap-1.5 opacity-40 cursor-not-allowed"
          title="Available when research is complete"
        >
          <Download size={12} />
          Export
        </Button>
      )}

      {/* Reset zoom icon for when zoom != 1 */}
      {zoom !== 1.0 && (
        <Button
          onClick={onZoomReset}
          className="h-7 w-7 p-0 bg-transparent hover:bg-[#21262d] text-[#7d8590] hover:text-[#e6edf3] border-0 rounded-[6px]"
          title="Reset zoom to 100%"
        >
          <RotateCcw size={12} />
        </Button>
      )}
    </div>
  );
}
