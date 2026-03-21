import { useEffect, useRef } from "react";
import { AnimatedMessageWrapper } from "./AnimatedMessageWrapper";
import { UserMessageBubble } from "./UserMessageBubble";
import { AgentThoughtBubble } from "./AgentThoughtBubble";
import { SurveyResultCard } from "./SurveyResultCard";
import { ClarifyingQuestionBubble } from "./ClarifyingQuestionBubble";
import { ThinkingBubble } from "./ThinkingBubble";
import type { ChatMessage } from "../types";

interface Props {
  messages: ChatMessage[];
  showThinking: boolean;
}

export function ChatMessageList({ messages, showThinking }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, showThinking]);

  return (
    <div className="flex-1 overflow-y-auto py-4 space-y-1">
      {messages.map((message) => (
        <AnimatedMessageWrapper key={message.id}>
          {message.type === "user_message" && (
            <UserMessageBubble message={message} />
          )}
          {message.type === "agent_thought" && (
            <AgentThoughtBubble message={message} />
          )}
          {message.type === "survey_result" && (
            <SurveyResultCard message={message} />
          )}
          {message.type === "clarifying_question" && (
            <ClarifyingQuestionBubble message={message} />
          )}
        </AnimatedMessageWrapper>
      ))}
      {showThinking && (
        <AnimatedMessageWrapper>
          <ThinkingBubble />
        </AnimatedMessageWrapper>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
