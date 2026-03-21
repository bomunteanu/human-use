import ReactMarkdown from "react-markdown";
import type { AgentThought } from "../types";

interface Props {
  message: AgentThought;
}

export function AgentThoughtBubble({ message }: Props) {
  return (
    <div className="flex justify-start px-4 py-1">
      <div className="max-w-[80%] rounded-[18px] rounded-tl-[4px] bg-[#161b22] border border-[#21262d] px-4 py-2.5">
        <div className="text-[13px] text-[#e6edf3] leading-relaxed prose prose-invert prose-sm max-w-none
          [&_p]:my-0.5 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5
          [&_code]:bg-[#21262d] [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-[12px]
          [&_strong]:text-[#e6edf3] [&_em]:text-[#7d8590]">
          <ReactMarkdown>{message.text}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
