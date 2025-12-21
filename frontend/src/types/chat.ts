export interface ReasoningStep {
  action: string;
  input: string;
  output?: string;
  thought?: string;
}

export interface Feedback {
  isPositive: boolean;
  category?: string;
  comment?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  reasoningSteps?: ReasoningStep[];
  feedback?: Feedback;
  citations?: string[];
}
