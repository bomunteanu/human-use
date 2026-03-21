import { ResearchProvider, useResearchContext } from "./context/ResearchContext";
import { Sidebar } from "./components/Sidebar";
import { ChatPane } from "./components/ChatPane";
import { PdfPanel } from "./components/PdfPanel";

function AppLayout() {
  const { state } = useResearchContext();
  const { isPdfPanelOpen } = state;

  return (
    <div className="flex h-screen bg-[#0d1117] overflow-hidden">
      <Sidebar />
      <ChatPane />
      {/* PDF panel: never unmounted, compressed via CSS width transition */}
      <div
        className={`
          flex-shrink-0 overflow-hidden border-l border-[#21262d]
          transition-all duration-300 ease-in-out
          ${isPdfPanelOpen ? "w-[440px] opacity-100" : "w-0 opacity-0"}
        `}
      >
        <PdfPanel />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ResearchProvider>
      <AppLayout />
    </ResearchProvider>
  );
}
