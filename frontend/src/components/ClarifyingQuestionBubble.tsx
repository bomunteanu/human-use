import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useResearchContext } from "../context/ResearchContext";
import type { ClarifyingQuestion } from "../types";

interface Props {
  message: ClarifyingQuestion;
}

export function ClarifyingQuestionBubble({ message }: Props) {
  const { submitAnswer } = useResearchContext();
  const [showOther, setShowOther] = useState(false);
  const [otherText, setOtherText] = useState("");

  const answered = message.answeredWith !== null;

  const handleOption = (opt: string) => {
    if (answered) return;
    if (opt === "Other (please specify)") {
      setShowOther(true);
    } else {
      submitAnswer(message.questionIndex, opt);
    }
  };

  const handleOtherSubmit = () => {
    const trimmed = otherText.trim();
    if (trimmed) submitAnswer(message.questionIndex, trimmed);
  };

  return (
    <div className="flex justify-start px-4 py-1">
      <div className="max-w-[80%] rounded-[12px] rounded-tl-[4px] bg-[#161b22] border border-[#2f81f7]/40 overflow-hidden">
        <div className="px-4 py-3 space-y-3">
          <p className="text-[13px] text-[#e6edf3] leading-snug">{message.question}</p>

          {answered ? (
            /* Answered state — static, non-interactive */
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-[#7d8590]">You answered:</span>
              <span className="text-[12px] font-medium text-[#2f81f7] bg-[#2f81f7]/10 px-2 py-0.5 rounded-full">
                {message.answeredWith}
              </span>
            </div>
          ) : (
            /* Pending state — interactive buttons */
            <div className="flex flex-col gap-1.5">
              {message.options.map((opt) => (
                <Button
                  key={opt}
                  onClick={() => handleOption(opt)}
                  className="h-8 px-3 text-[13px] text-left justify-start bg-[#0d1117] hover:bg-[#21262d] text-[#e6edf3] border border-[#30363d] hover:border-[#2f81f7] rounded-[6px] transition-colors"
                >
                  {opt}
                </Button>
              ))}
              {showOther && (
                <div className="flex gap-2 mt-1">
                  <Input
                    autoFocus
                    value={otherText}
                    onChange={(e) => setOtherText(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleOtherSubmit()}
                    placeholder="Please specify..."
                    className="flex-1 h-8 text-[13px] bg-[#0d1117] border-[#21262d] text-[#e6edf3] placeholder:text-[#7d8590] focus-visible:ring-[#2f81f7]"
                  />
                  <Button
                    onClick={handleOtherSubmit}
                    disabled={!otherText.trim()}
                    className="h-8 px-3 text-[13px] bg-[#2f81f7] hover:bg-[#388bfd] text-white border-0 rounded-[6px] disabled:opacity-40"
                  >
                    Submit
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
