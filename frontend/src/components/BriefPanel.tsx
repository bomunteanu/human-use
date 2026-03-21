import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { BriefSection } from "../types";

interface Props {
  sections: BriefSection[];
  isDone: boolean;
}

const PLACEHOLDER_SECTIONS = ["Overview", "Key Findings", "Data Summary", "Conclusions"];

export function BriefPanel({ sections, isDone }: Props) {
  const lockedCount = sections.length;

  return (
    <Card className="flex flex-col h-full bg-[#161b22] border-[#21262d] rounded-[6px]">
      <div className="px-4 py-3 border-b border-[#21262d] flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-[#e6edf3]">Research Brief</h2>
        {isDone && (
          <span className="text-[11px] text-[#3fb950] font-medium">Complete</span>
        )}
      </div>
      <ScrollArea className="flex-1 px-4 py-3">
        {sections.length === 0 && !isDone ? (
          <div className="space-y-4">
            {PLACEHOLDER_SECTIONS.map((title) => (
              <div key={title} className="opacity-30">
                <h3 className="text-[13px] font-semibold text-[#7d8590] mb-1">{title}</h3>
                <div className="space-y-1.5">
                  {[80, 60, 70].map((w, i) => (
                    <div key={i} className="h-2 rounded bg-[#21262d]" style={{ width: `${w}%` }} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {sections.map((section, i) => (
              <div key={i}>
                {i > 0 && <Separator className="mb-4 bg-[#21262d]" />}
                <h3 className="text-[13px] font-semibold text-[#e6edf3] mb-2">{section.title}</h3>
                <p className="text-[13px] text-[#7d8590] leading-relaxed whitespace-pre-wrap">{section.content}</p>
              </div>
            ))}
            {!isDone && lockedCount < PLACEHOLDER_SECTIONS.length && (
              <div className="opacity-30">
                {PLACEHOLDER_SECTIONS.slice(lockedCount).map((title) => (
                  <div key={title} className="mt-4">
                    <Separator className="mb-4 bg-[#21262d]" />
                    <h3 className="text-[13px] font-semibold text-[#7d8590] mb-1">{title}</h3>
                    <div className="space-y-1.5">
                      {[80, 60, 70].map((w, i) => (
                        <div key={i} className="h-2 rounded bg-[#21262d]" style={{ width: `${w}%` }} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </ScrollArea>
    </Card>
  );
}
