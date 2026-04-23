import { useEffect, useRef } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Loader2 } from "lucide-react";
import { useResearchContext } from "../context/ResearchContext";
import type { ImageABTest } from "../types";
import { WorldMap } from "./WorldMap";

interface Props {
  message: ImageABTest;
}

export function ImageABTestBubble({ message }: Props) {
  const { setChartCapture } = useResearchContext();
  const { order, prompt_a, prompt_b, image_a_b64, image_b_b64 } = message;
  const containerRef = useRef<HTMLDivElement>(null);
  const capturedRef = useRef(false);

  // Capture bar-chart SVG as PNG when order completes — same retry logic as SurveyResultCard
  useEffect(() => {
    if (!order.distribution || !order.is_complete || capturedRef.current) return;

    let cancelled = false;

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
          if (cancelled) {
            URL.revokeObjectURL(url);
            return;
          }
          const canvas = document.createElement("canvas");
          canvas.width = rect.width * 2;
          canvas.height = rect.height * 2;
          const ctx = canvas.getContext("2d");
          if (!ctx) {
            URL.revokeObjectURL(url);
            return;
          }
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
    return () => {
      cancelled = true;
    };
  }, [order.distribution, order.is_complete, order.order_id, setChartCapture]);

  const winnerLabel =
    order.winner === "option_a" ? "A" : order.winner === "option_b" ? "B" : null;

  return (
    <div className="flex justify-start px-4 py-1">
      <div className="max-w-[90%] w-full rounded-[12px] rounded-tl-[4px] bg-[#161b22] border border-[#21262d] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#21262d]">
          {order.is_complete ? (
            <span className="text-[11px] font-medium text-[#3fb950]">
              Image A/B test complete
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-[11px] font-medium text-[#7d8590]">
              <Loader2 size={11} className="animate-spin" />
              {order.status === "dispatched" ? "Generating images…" : order.status}
            </span>
          )}
          {order.n_responses != null && (
            <span className="text-[11px] text-[#7d8590]">
              {order.n_responses} responses
            </span>
          )}
        </div>

        <div className="px-4 py-3 space-y-3">
          {/* Images side by side */}
          <div className="grid grid-cols-2 gap-3">
            {/* Image A */}
            <div className="space-y-2">
              <div className="relative rounded-md overflow-hidden bg-[#0d1117] border border-[#21262d]">
                <img
                  src={`data:image/png;base64,${image_a_b64}`}
                  alt="Image A"
                  className="w-full h-auto object-cover"
                />
                {order.is_complete && winnerLabel === "A" && (
                  <div className="absolute top-2 right-2 bg-[#3fb950] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                    Winner
                  </div>
                )}
              </div>
              <div className="space-y-0.5">
                <p className="text-[10px] font-medium text-[#7d8590] uppercase tracking-wide">
                  Image A
                </p>
                <p className="text-[11px] text-[#e6edf3] leading-snug line-clamp-3">
                  {prompt_a}
                </p>
                {order.is_complete && order.distribution && (
                  <p className="text-[11px] text-[#2f81f7] font-medium">
                    {order.distribution["option_a"] ?? 0} votes
                  </p>
                )}
              </div>
            </div>

            {/* Image B */}
            <div className="space-y-2">
              <div className="relative rounded-md overflow-hidden bg-[#0d1117] border border-[#21262d]">
                <img
                  src={`data:image/png;base64,${image_b_b64}`}
                  alt="Image B"
                  className="w-full h-auto object-cover"
                />
                {order.is_complete && winnerLabel === "B" && (
                  <div className="absolute top-2 right-2 bg-[#3fb950] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                    Winner
                  </div>
                )}
              </div>
              <div className="space-y-0.5">
                <p className="text-[10px] font-medium text-[#7d8590] uppercase tracking-wide">
                  Image B
                </p>
                <p className="text-[11px] text-[#e6edf3] leading-snug line-clamp-3">
                  {prompt_b}
                </p>
                {order.is_complete && order.distribution && (
                  <p className="text-[11px] text-[#2f81f7] font-medium">
                    {order.distribution["option_b"] ?? 0} votes
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Bar chart — shown once results start arriving */}
          {order.distribution ? (
            <>
              <div ref={containerRef}>
                <ResponsiveContainer width="100%" height={90}>
                  <BarChart
                    data={[
                      { name: "Image A", value: order.distribution["option_a"] ?? 0 },
                      { name: "Image B", value: order.distribution["option_b"] ?? 0 },
                    ]}
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
                    <Bar dataKey="value" radius={[3, 3, 0, 0]} isAnimationActive={!order.is_complete}>
                      <Cell
                        fill={order.winner === "option_a" ? "#3fb950" : "#2f81f7"}
                      />
                      <Cell
                        fill={order.winner === "option_b" ? "#3fb950" : "#2f81f7"}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {!order.is_complete && (
                <p className="text-[11px] text-[#7d8590]">Still collecting responses…</p>
              )}
            </>
          ) : !order.is_complete ? (
            <div className="space-y-1.5 py-1">
              <div className="h-1.5 rounded-full bg-[#21262d] overflow-hidden">
                <div className="h-full w-1/2 bg-[#2f81f7] rounded-full animate-pulse" />
              </div>
              <p className="text-[11px] text-[#7d8590]">Collecting votes from real people…</p>
            </div>
          ) : null}

          {/* World map */}
          <WorldMap countryCounts={order.country_counts ?? {}} />
        </div>
      </div>
    </div>
  );
}
