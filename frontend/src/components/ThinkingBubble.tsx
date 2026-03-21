export function ThinkingBubble() {
  return (
    <div className="flex justify-start px-4 py-1">
      <div className="rounded-[18px] rounded-tl-[4px] bg-[#161b22] border border-[#21262d] px-4 py-3.5">
        <div className="flex gap-1.5 items-center">
          <span className="w-2 h-2 rounded-full bg-[#7d8590] animate-bounce [animation-delay:-0.3s]" />
          <span className="w-2 h-2 rounded-full bg-[#7d8590] animate-bounce [animation-delay:-0.15s]" />
          <span className="w-2 h-2 rounded-full bg-[#7d8590] animate-bounce" />
        </div>
      </div>
    </div>
  );
}
