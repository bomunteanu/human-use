// ─── Demographic targeting types ─────────────────────────────────────────────

export type AgeGroup = "under_18" | "18-24" | "25-34" | "35-44" | "45-54" | "55+";
export type Gender = "male" | "female" | "other";

export interface TargetingConfig {
  country_codes: string[];
  languages: string[];
  age_groups: AgeGroup[];
  genders: Gender[];
}

export function emptyTargeting(): TargetingConfig {
  return { country_codes: [], languages: [], age_groups: [], genders: [] };
}

// ─── Anthropic conversation history types ────────────────────────────────────

export type AnthropicContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_use"; id: string; name: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool_use_id: string; content: string; is_error?: boolean };

export interface AnthropicMessage {
  role: "user" | "assistant";
  content: string | AnthropicContentBlock[];
}

// ─── SSE event types ─────────────────────────────────────────────────────────

export interface ClarifyingQuestionEvent {
  event: "clarifying_question";
  session_id: string;
  question_index: number;
  question: string;
  options: string[];  // always 4 items
}

export interface AgentThoughtEvent {
  event: "agent_thought";
  text: string;
}

export interface TargetingUpdateEvent {
  event: "targeting_update";
  country_codes: string[];
  languages: string[];
  age_groups: AgeGroup[];
  genders: Gender[];
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
  title: string;
}

export interface DoneEvent {
  event: "done";
  brief: ResearchBrief;
  messages: AnthropicMessage[];
}

export type SSEEvent =
  | ClarifyingQuestionEvent
  | AgentThoughtEvent
  | TargetingUpdateEvent
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

// ─── Chat message union ───────────────────────────────────────────────────────

export interface UserMessage {
  id: string;
  type: "user_message";
  text: string;
  timestamp: number;
}

export interface AgentThought {
  id: string;
  type: "agent_thought";
  text: string; // raw markdown
  timestamp: number;
}

export interface SurveyResult {
  id: string;
  type: "survey_result";
  order: OrderState; // full snapshot at order_complete
  chartCapture: string | null; // null until SVG captured
  timestamp: number;
}

export interface ClarifyingQuestion {
  id: string;
  type: "clarifying_question";
  sessionId: string;
  questionIndex: number;
  question: string;
  options: string[]; // always 4
  answeredWith: string | null; // null = pending; string = user's answer
  timestamp: number;
}

export type ChatMessage = UserMessage | AgentThought | SurveyResult | ClarifyingQuestion;

// ─── Session history ──────────────────────────────────────────────────────────

export interface SessionSummary {
  id: string;
  title: string;
  created_at: string; // ISO 8601
  brief: ResearchBrief | null;
}
