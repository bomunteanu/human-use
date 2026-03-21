import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import type { AgentThoughtEvent } from "../types";
import { useEffect, useRef } from "react";

interface Props {
  thoughts: AgentThoughtEvent[];
}

export function ThoughtStream({ thoughts }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thoughts]);

  return (
    <Card className="flex flex-col h-full bg-[#161b22] border-[#21262d] rounded-[6px]">
      <div className="px-4 py-3 border-b border-[#21262d]">
        <h2 className="text-[15px] font-semibold text-[#e6edf3]">Agent Thoughts</h2>
      </div>
      <ScrollArea className="flex-1 px-4 py-3">
        {thoughts.length === 0 ? (
          <p className="text-[#7d8590] text-[13px]">Waiting for agent...</p>
        ) : (
          <div className="space-y-3">
            {thoughts.map((t, i) => (
              <p key={i} className="text-[13px] text-[#e6edf3] leading-relaxed whitespace-pre-wrap">
                {t.text}
              </p>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </ScrollArea>
    </Card>
  );
}
