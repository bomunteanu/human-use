import { useEffect, useRef } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Loader2 } from "lucide-react";
import { useResearchContext } from "../context/ResearchContext";
import type { SurveyResult } from "../types";

interface Props {
  message: SurveyResult;
}

const TOOL_LABEL: Record<string, string> = {
  ask_free_text: "Free Text",
  ask_multiple_choice: "Multiple Choice",
  compare: "Compare",
  rank: "Rank",
};

export function SurveyResultCard({ message }: Props) {
  const { setChartCapture } = useResearchContext();
  const { order } = message;
  const containerRef = useRef<HTMLDivElement>(null);
  const capturedRef = useRef(false);

  useEffect(() => {
    if (!order.distribution || capturedRef.current) return;

    let cancelled = false;

    // recharts uses ResizeObserver to set SVG dimensions asynchronously,
    // so a single rAF may fire before the SVG has non-zero dimensions.
    // Retry up to 10 times with 150 ms gaps.
    const attempt = (retriesLeft: number) => {
      requestAnimationFrame(() => {
        if (cancelled || capturedRef.current) return;

        const svg = containerRef.current?.querySelector("svg");
        const rect = svg?.getBoundingClientRect();

        if (!svg || !rect || rect.width === 0) {
          if (retriesLeft > 0) {
            setTimeout(() => attempt(retriesLeft - 1), 150);
          }
          return;
        }

        const xml = new XMLSerializer().serializeToString(svg);
        const blob = new Blob([xml], { type: "image/svg+xml" });
        const url = URL.createObjectURL(blob);
        const img = new window.Image();

        img.onload = () => {
          if (cancelled) { URL.revokeObjectURL(url); return; }
          const canvas = document.createElement("canvas");
          canvas.width = rect.width * 2;
          canvas.height = rect.height * 2;
          const ctx = canvas.getContext("2d");
          if (!ctx) { URL.revokeObjectURL(url); return; }
          ctx.scale(2, 2);
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, rect.width, rect.height);
          ctx.drawImage(img, 0, 0, rect.width, rect.height);
          URL.revokeObjectURL(url);
          capturedRef.current = true;
          setChartCapture(order.order_id, canvas.toDataURL("image/png"));
        };

        img.onerror = () => URL.revokeObjectURL(url);
        img.src = url;
      });
    };

    attempt(10);
    return () => { cancelled = true; };
  }, [order.distribution, order.order_id, setChartCapture]);

  return (
    <div className="flex justify-start px-4 py-1">
      <div className="max-w-[85%] w-full rounded-[12px] rounded-tl-[4px] bg-[#161b22] border border-[#21262d] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#21262d]">
          {order.is_complete ? (
            <span className="text-[11px] font-medium text-[#3fb950]">Survey complete</span>
          ) : (
            <span className="flex items-center gap-1.5 text-[11px] font-medium text-[#7d8590]">
              <Loader2 size={11} className="animate-spin" />
              {order.status === "dispatched" ? "Dispatching survey…" : order.status}
            </span>
          )}
          <span className="text-[11px] text-[#7d8590]">
            {TOOL_LABEL[order.tool] ?? order.tool}
            {order.n_responses != null && (
              <span className="ml-2">· {order.n_responses} responses</span>
            )}
          </span>
        </div>

        <div className="px-4 py-3 space-y-3">
          {/* Question */}
          <p className="text-[13px] text-[#e6edf3] leading-snug">{order.question}</p>

          {order.is_complete ? (
            <>
              {/* Winner badge */}
              {order.winner && (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-[#7d8590]">Top response:</span>
                  <span className="text-[12px] font-medium text-[#3fb950] bg-[#3fb950]/10 px-2 py-0.5 rounded-full">
                    {order.winner}
                  </span>
                </div>
              )}

              {/* Chart */}
              {order.distribution ? (
                <div ref={containerRef}>
                  <ResponsiveContainer width="100%" height={110}>
                    <BarChart
                      data={Object.entries(order.distribution).map(([name, value]) => ({ name, value }))}
                      margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
                    >
                      <XAxis dataKey="name" tick={{ fill: "#7d8590", fontSize: 11 }} />
                      <YAxis tick={{ fill: "#7d8590", fontSize: 11 }} />
                      <Tooltip
                        contentStyle={{
                          background: "#0d1117",
                          border: "1px solid #21262d",
                          borderRadius: 4,
                          fontSize: 12,
                        }}
                        labelStyle={{ color: "#e6edf3" }}
                      />
                      <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                        {Object.keys(order.distribution).map((name, i) => (
                          <Cell
                            key={i}
                            fill={name === order.winner ? "#3fb950" : "#2f81f7"}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-[12px] text-[#7d8590]">
                  {order.n_responses != null ? `${order.n_responses} responses collected` : "Complete"}
                </p>
              )}
            </>
          ) : (
            /* In-progress skeleton */
            <div className="space-y-1.5 py-1">
              <div className="h-1.5 rounded-full bg-[#21262d] overflow-hidden">
                <div className="h-full w-1/2 bg-[#2f81f7] rounded-full animate-pulse" />
              </div>
              <p className="text-[11px] text-[#7d8590]">Collecting responses from real people…</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
