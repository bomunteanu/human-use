import { useState } from "react";
import { PDFViewer, type DocumentProps } from "@react-pdf/renderer";
import type { ReactElement } from "react";
import { PdfToolbar } from "./PdfToolbar";
import { ResearchPdfDocument } from "./ResearchPdfDocument";
import { useResearchContext } from "../context/ResearchContext";

export function PdfPanel() {
  const { state, dispatch } = useResearchContext();
  const [zoom, setZoom] = useState(1.0);

  const { currentQuestion, sections, orders, chartCaptures, isDone, brief } = state;

  const completedOrders = [...orders.values()].filter(
    (o) => o.is_complete && chartCaptures.has(o.order_id),
  );

  const pdfTitle = brief?.title || currentQuestion || "Research Brief";
  const filename = `${pdfTitle.slice(0, 40).replace(/\s+/g, "_")}_brief.pdf`;

  const doc = (
    <ResearchPdfDocument
      title={pdfTitle}
      sections={sections}
      completedOrders={completedOrders}
      svgCaptures={chartCaptures}
    />
  ) as ReactElement<DocumentProps>;

  const handleZoomIn = () => setZoom((z) => Math.min(2.0, Math.round((z + 0.25) * 100) / 100));
  const handleZoomOut = () => setZoom((z) => Math.max(0.5, Math.round((z - 0.25) * 100) / 100));
  const handleZoomReset = () => setZoom(1.0);
  const handleClose = () => dispatch({ type: "CLOSE_PDF_PANEL" });

  const PLACEHOLDER_SECTIONS = ["Overview", "Key Findings", "Data Summary", "Conclusions"];

  return (
    <div className="flex flex-col h-full bg-[#161b22]">
      <PdfToolbar
        zoom={zoom}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onZoomReset={handleZoomReset}
        onClose={handleClose}
        isDone={isDone}
        filename={filename}
        pdfDocument={doc}
      />

      <div className="flex-1 min-h-0">
        {sections.length === 0 ? (
          /* Skeleton before first section arrives */
          <div className="px-5 py-5 space-y-5">
            {PLACEHOLDER_SECTIONS.map((title) => (
              <div key={title} className="opacity-25">
                <div className="h-3 rounded bg-[#21262d] w-1/3 mb-2" />
                <div className="space-y-1.5">
                  {[80, 60, 70].map((w, i) => (
                    <div key={i} className="h-2 rounded bg-[#21262d]" style={{ width: `${w}%` }} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <PDFViewer
            width="100%"
            height="100%"
            style={{ border: "none" }}
            // @ts-expect-error — scale prop is supported in @react-pdf/renderer v3+
            scale={zoom}
          >
            {doc}
          </PDFViewer>
        )}
      </div>
    </div>
  );
}
