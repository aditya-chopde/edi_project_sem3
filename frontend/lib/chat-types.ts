export type ResponseLanguage =
  | "English"
  | "Hindi"
  | "Marathi"
  | "Hinglish"
  | "Sanskrit";

export type RetrievalMode = "Cross-language" | "Hybrid" | "Same-language";

export type MessageStatus =
  | "pending"
  | "streaming"
  | "completed"
  | "stopped"
  | "failed";

export type ChatSource = {
  id: string;
  documentId: string;
  title: string;
  languageScript: string;
  pageSection: string;
  snippet: string;
  relevanceScore?: number;
  isIllustrative: true;
};

export type ChatAttachment = {
  name: string;
  size: number;
  type: string;
};

export type ChatMessage = {
  id: string;
  conversationId: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  status: MessageStatus;
  sources: ChatSource[];
  language: ResponseLanguage;
  errorDetails?: string;
  attachment?: ChatAttachment;
  feedback?: "up" | "down";
};

export type Conversation = {
  id: string;
  title: string;
  pinned: boolean;
  saved: boolean;
  timestamp: number;
  messages: ChatMessage[];
};
