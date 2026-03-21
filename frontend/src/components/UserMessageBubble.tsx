import type { UserMessage } from "../types";

interface Props {
  message: UserMessage;
}

export function UserMessageBubble({ message }: Props) {
  return (
    <div className="flex justify-end px-4 py-1">
      <div className="max-w-[75%] rounded-[18px] rounded-tr-[4px] bg-[#2f81f7] px-4 py-2.5">
        <p className="text-[14px] text-white leading-relaxed whitespace-pre-wrap">
          {message.text}
        </p>
      </div>
    </div>
  );
}
