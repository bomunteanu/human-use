import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { TargetingSelector } from "./TargetingSelector";

interface Props {
  value: string;
  onChange: (v: string) => void;
  countryCodes: string[];
  onCountryCodesChange: (codes: string[]) => void;
  onSubmit: () => void;
  onStop: () => void;
  onCompileFindings: () => void;
  isStreaming: boolean;
  hasOrders: boolean;
  hasSections: boolean;
  disabled: boolean;
}

export function ChatInputBar({
  value,
  onChange,
  countryCodes,
  onCountryCodesChange,
  onSubmit,
  onStop,
  onCompileFindings,
  isStreaming,
  hasOrders,
  hasSections,
  disabled,
}: Props) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !isStreaming) onSubmit();
    }
  };

  return (
    <div className="px-4 py-3 border-t border-[#21262d] bg-[#0d1117]">
      <div className="max-w-3xl mx-auto space-y-2">
        {/* Audience row */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[#7d8590]">Audience:</span>
          <TargetingSelector
            value={countryCodes}
            onChange={onCountryCodesChange}
            disabled={isStreaming}
          />
        </div>

        {/* Input + buttons row */}
        <div className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a research question..."
              disabled={isStreaming || disabled}
              rows={1}
              className="w-full resize-none rounded-[10px] bg-[#161b22] border border-[#21262d] text-[14px] text-[#e6edf3] placeholder:text-[#7d8590]
                px-4 py-2.5 outline-none focus:border-[#2f81f7] transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                min-h-[42px] max-h-[160px] overflow-y-auto leading-relaxed"
              style={{ fieldSizing: "content" } as React.CSSProperties}
            />
          </div>

          {isStreaming ? (
            <Button
              type="button"
              onClick={onStop}
              className="h-[42px] px-4 text-[13px] bg-[#21262d] hover:bg-[#30363d] text-[#e6edf3] border border-[#30363d] rounded-[10px] flex-shrink-0"
            >
              Stop
            </Button>
          ) : (
            <Button
              type="button"
              onClick={onSubmit}
              disabled={!value.trim() || disabled}
              className="h-[42px] px-4 text-[13px] bg-[#2f81f7] hover:bg-[#388bfd] text-white border-0 rounded-[10px] flex-shrink-0 disabled:opacity-40"
            >
              Send
            </Button>
          )}

          {hasSections && !isStreaming ? (
            <Button
              type="button"
              onClick={onCompileFindings}
              title="Reopen the research brief"
              className="h-[42px] px-4 text-[13px] bg-[#161b22] hover:bg-[#21262d] text-[#e6edf3]
                border border-[#3fb950]/50 hover:border-[#3fb950] rounded-[10px] flex-shrink-0 transition-colors"
            >
              View Brief
            </Button>
          ) : (
            <Button
              type="button"
              onClick={onCompileFindings}
              disabled={!isStreaming || !hasOrders}
              title="Synthesize everything collected so far into a research brief"
              className="h-[42px] px-4 text-[13px] bg-[#161b22] hover:bg-[#21262d] text-[#e6edf3]
                border border-[#30363d] hover:border-[#3fb950] rounded-[10px] flex-shrink-0
                disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Compile Findings
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
