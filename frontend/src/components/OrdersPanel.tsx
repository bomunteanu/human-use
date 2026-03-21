import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { OrderState } from "../types";

interface Props {
  orders: Map<string, OrderState>;
}

const TOOL_LABEL: Record<string, string> = {
  ask_free_text: "Free Text",
  ask_multiple_choice: "Multiple Choice",
  compare: "Compare",
  rank: "Rank",
};

function OrderCard({ order }: { order: OrderState }) {
  if (order.is_complete && order.distribution) {
    const data = Object.entries(order.distribution).map(([name, value]) => ({ name, value }));
    return (
      <div className="border border-[#21262d] rounded-[6px] p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[#7d8590] text-[11px] font-mono">{order.order_id}</span>
          <span className="text-[11px] text-[#3fb950] font-medium">{TOOL_LABEL[order.tool] ?? order.tool}</span>
        </div>
        <p className="text-[13px] text-[#e6edf3]">{order.question}</p>
        {order.winner && (
          <p className="text-[12px] text-[#7d8590]">
            Winner: <span className="text-[#3fb950] font-medium">{order.winner}</span>
            {order.n_responses != null && <span className="ml-2">({order.n_responses} responses)</span>}
          </p>
        )}
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <XAxis dataKey="name" tick={{ fill: "#7d8590", fontSize: 11 }} />
            <YAxis tick={{ fill: "#7d8590", fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: "#161b22", border: "1px solid #21262d", borderRadius: 4, fontSize: 12 }}
              labelStyle={{ color: "#e6edf3" }}
            />
            <Bar dataKey="value" radius={[3, 3, 0, 0]}>
              {data.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.name === order.winner ? "#3fb950" : "#2f81f7"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (order.is_complete) {
    return (
      <div className="border border-[#21262d] rounded-[6px] p-3 space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[#7d8590] text-[11px] font-mono">{order.order_id}</span>
          <span className="text-[11px] text-[#3fb950] font-medium">Complete</span>
        </div>
        <p className="text-[13px] text-[#e6edf3]">{order.question}</p>
        {order.n_responses != null && (
          <p className="text-[12px] text-[#7d8590]">{order.n_responses} responses</p>
        )}
      </div>
    );
  }

  return (
    <div className="border border-[#21262d] rounded-[6px] p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[#7d8590] text-[11px] font-mono">{order.order_id}</span>
        <span className="text-[11px] text-[#7d8590]">{TOOL_LABEL[order.tool] ?? order.tool}</span>
      </div>
      <p className="text-[13px] text-[#e6edf3]">{order.question}</p>
      <div className="space-y-1">
        <div className="flex justify-between text-[11px] text-[#7d8590]">
          <span>{order.status}</span>
        </div>
        <Progress
          value={order.status === "dispatched" ? 10 : 50}
          className="h-1.5 bg-[#21262d] [&>div]:bg-[#2f81f7]"
        />
      </div>
    </div>
  );
}

export function OrdersPanel({ orders }: Props) {
  const list = Array.from(orders.values());

  return (
    <Card className="flex flex-col h-full bg-[#161b22] border-[#21262d] rounded-[6px]">
      <div className="px-4 py-3 border-b border-[#21262d]">
        <h2 className="text-[15px] font-semibold text-[#e6edf3]">
          Active Orders{list.length > 0 && <span className="ml-2 text-[#7d8590] font-normal text-[13px]">({list.length})</span>}
        </h2>
      </div>
      <ScrollArea className="flex-1 px-4 py-3">
        {list.length === 0 ? (
          <p className="text-[#7d8590] text-[13px]">No orders yet...</p>
        ) : (
          <div className="space-y-3">
            {list.map((o) => (
              <OrderCard key={o.order_id} order={o} />
            ))}
          </div>
        )}
      </ScrollArea>
    </Card>
  );
}
