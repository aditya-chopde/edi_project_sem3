export type ResponseLanguage =
  | "English"
  | "Hindi"
  | "Marathi"
  | "Hinglish"
  | "Sanskrit";

export type RetrievalMode = "Hybrid";

export type MessageStatus =
  | "pending"
  | "uploading"
  | "indexing"
  | "querying"
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
  progressDetail?: string;
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
