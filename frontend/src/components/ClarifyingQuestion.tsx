import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ClarifyingQuestionEvent } from "../types";

interface Props {
  question: ClarifyingQuestionEvent;
  onAnswer: (questionIndex: number, answer: string) => void;
}

export function ClarifyingQuestion({ question: cq, onAnswer }: Props) {
  const [showOther, setShowOther] = useState(false);
  const [otherText, setOtherText] = useState("");

  const handleOption = (opt: string) => {
    if (opt === "Other (please specify)") {
      setShowOther(true);
    } else {
      onAnswer(cq.question_index, opt);
    }
  };

  const handleOtherSubmit = () => {
    const trimmed = otherText.trim();
    if (trimmed) {
      onAnswer(cq.question_index, trimmed);
    }
  };

  return (
    <div className="border border-[#2f81f7] rounded-[6px] bg-[#0d1117] p-4 mb-3">
      <p className="text-[13px] font-medium text-[#e6edf3] mb-3">{cq.question}</p>
      <div className="flex flex-col gap-2">
        {cq.options.map((opt) => (
          <Button
            key={opt}
            onClick={() => handleOption(opt)}
            className="h-8 px-3 text-[13px] text-left justify-start bg-[#161b22] hover:bg-[#21262d] text-[#e6edf3] border border-[#30363d] hover:border-[#2f81f7] rounded-[6px] transition-colors"
          >
            {opt}
          </Button>
        ))}
      </div>
      {showOther && (
        <div className="flex gap-2 mt-3">
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
  );
}
