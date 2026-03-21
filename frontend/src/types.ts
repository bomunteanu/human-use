export interface AgentThoughtEvent {
  event: "agent_thought";
  text: string;
}

export interface OrderDispatchedEvent {
  event: "order_dispatched";
  order_id: string;
  tool: string;
  question: string;
}

export interface OrderProgressEvent {
  event: "order_progress";
  order_id: string;
  status: string;
  is_complete: boolean;
}

export interface OrderCompleteEvent {
  event: "order_complete";
  order_id: string;
  distribution: Record<string, number> | null;
  winner: string | null;
  n_responses: number;
}

export interface BriefSection {
  title: string;
  content: string;
}

export interface BriefUpdateEvent {
  event: "brief_update";
  section: BriefSection;
}

export interface ResearchBrief {
  question: string;
  sections: BriefSection[];
  summary: string;
}

export interface DoneEvent {
  event: "done";
  brief: ResearchBrief;
}

export type SSEEvent =
  | AgentThoughtEvent
  | OrderDispatchedEvent
  | OrderProgressEvent
  | OrderCompleteEvent
  | BriefUpdateEvent
  | DoneEvent;

export interface OrderState {
  order_id: string;
  tool: string;
  question: string;
  status: string;
  is_complete: boolean;
  distribution: Record<string, number> | null;
  winner: string | null;
  n_responses: number | null;
}
