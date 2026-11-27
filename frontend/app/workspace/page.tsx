"use client";

import {
  ArrowUp,
  BookOpen,
  Bookmark,
  Check,
  ChevronDown,
  CircleHelp,
  Copy,
  FileText,
  FlaskConical,
  Globe2,
  Library,
  LoaderCircle,
  Menu,
  MessageSquarePlus,
  MoreHorizontal,
  Network,
  Paperclip,
  PanelLeftClose,
  Pin,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatMarkdown } from "@/components/chat-markdown";
import { Button } from "@/components/ui/button";
import {
  api,
  type ApiDocument,
  type ApiHealth,
  type QueryResponse,
  supportedDocumentExtensions,
} from "@/lib/api";
import type {
  ChatAttachment,
  ChatMessage,
  ChatSource,
  Conversation,
  ResponseLanguage,
  RetrievalMode,
} from "@/lib/chat-types";
import "./chat.css";

type WorkspaceView = "chat" | "archive" | "research" | "settings";

const STORAGE_KEY = "itihasa-ai-conversations-v1";
const responseLanguages: ResponseLanguage[] = [
  "English",
  "Hindi",
  "Marathi",
  "Hinglish",
  "Sanskrit",
];
const retrievalModes: RetrievalMode[] = ["Hybrid"];
const suggestions = [
  { prompt: "How do Sanskrit texts describe the purpose of learning?", script: "SANSKRIT · ENGLISH" },
  { prompt: "Find Persian records about trade in the Deccan.", script: "PERSIAN RECORDS" },
  { prompt: "मराठी ऐतिहासिक कागदपत्रांमधून काय समजते?", script: "मराठी" },
  { prompt: "What can Modi-script records tell us about daily life?", script: "MODI · OLD MARATHI" },
];

function makeId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function conversationTitle(question: string) {
  const normalized = question.trim().replace(/\s+/g, " ");
  return normalized.length > 46 ? `${normalized.slice(0, 43).trimEnd()}…` : normalized;
}

function apiErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function waitForDelay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("The request was cancelled.", "AbortError"));
      return;
    }
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("The request was cancelled.", "AbortError"));
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

function formatTime(timestamp: number) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(timestamp);
}

function Logo() {
  return (
    <div className="itihasa-logo">
      <span className="itihasa-logo-mark"><BookOpen size={18} /></span>
      <span>Itihasa <em>AI</em></span>
    </div>
  );
}

function IconButton({
  label,
  onClick,
  children,
  className = "",
  disabled = false,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <button
      aria-label={label}
      className={`itihasa-icon-button ${className}`}
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}

function Sidebar({
  conversations,
  selectedId,
  view,
  onSelectChat,
  onNewChat,
  onSelectView,
  onPin,
  onRename,
  onDelete,
  mobileOpen,
  onClose,
}: {
  conversations: Conversation[];
  selectedId: string | null;
  view: WorkspaceView;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  onSelectView: (view: WorkspaceView) => void;
  onPin: (id: string) => void;
  onRename: (id: string) => void;
  onDelete: (id: string) => void;
  mobileOpen: boolean;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const [savedOnly, setSavedOnly] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const filtered = useMemo(() => {
    return conversations
      .filter((conversation) => !savedOnly || conversation.saved)
      .filter((conversation) => conversation.title.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.timestamp - a.timestamp);
  }, [conversations, savedOnly, search]);

  const pickChat = (id: string) => {
    onSelectChat(id);
    onClose();
  };

  return (
    <>
      <button
        aria-label="Close navigation"
        className={`itihasa-mobile-scrim ${mobileOpen ? "is-open" : ""}`}
        onClick={onClose}
        type="button"
      />
      <aside className={`itihasa-sidebar ${mobileOpen ? "is-open" : ""}`}>
        <div className="itihasa-sidebar-head">
          <Logo />
          <IconButton label="Close navigation" className="itihasa-mobile-close" onClick={onClose}>
            <X size={18} />
          </IconButton>
        </div>
        <Button className="itihasa-new-chat" onClick={onNewChat}>
          <Plus data-icon="inline-start" /> New chat
        </Button>

        <div className="itihasa-side-nav">
          <span className="itihasa-side-label">Workspace</span>
          <button className={view === "archive" ? "is-active" : ""} onClick={() => onSelectView("archive")}>
            <Library size={17} /> Historical archive
          </button>
          <button className={view === "research" ? "is-active" : ""} onClick={() => onSelectView("research")}>
            <FlaskConical size={17} /> Research dashboard
          </button>
          <button className={savedOnly ? "is-active" : ""} onClick={() => setSavedOnly((value) => !value)}>
            <Bookmark size={17} /> Saved conversations
            {savedOnly && <span className="itihasa-filter-count">{filtered.length}</span>}
          </button>
          <button className={view === "settings" ? "is-active" : ""} onClick={() => onSelectView("settings")}>
            <Settings size={17} /> Settings
          </button>
        </div>

        <div className="itihasa-history">
          <div className="itihasa-history-heading">
            <span className="itihasa-side-label">{savedOnly ? "Saved conversations" : "Your conversations"}</span>
            <span className="itihasa-conversation-count">{filtered.length}</span>
          </div>
          <label className="itihasa-chat-search">
            <Search size={15} />
            <input
              aria-label="Search conversations"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search conversations"
              value={search}
            />
            {search && <IconButton label="Clear search" onClick={() => setSearch("")}><X size={13} /></IconButton>}
          </label>
          <div className="itihasa-history-list">
            {filtered.map((conversation) => (
              <div
                className={`itihasa-history-row ${selectedId === conversation.id && view === "chat" ? "is-selected" : ""}`}
                key={conversation.id}
              >
                <button className="itihasa-history-select" onClick={() => pickChat(conversation.id)}>
                  <span className="itihasa-history-title">
                    {conversation.pinned && <Pin size={12} />}
                    {conversation.title}
                  </span>
                  <span className="itihasa-history-date">{formatTime(conversation.timestamp)}</span>
                </button>
                <div className="itihasa-row-menu-wrap">
                  <IconButton
                    label={`Options for ${conversation.title}`}
                    onClick={() => setOpenMenu(openMenu === conversation.id ? null : conversation.id)}
                  >
                    <MoreHorizontal size={17} />
                  </IconButton>
                  {openMenu === conversation.id && (
                    <>
                      <button
                        className="itihasa-menu-dismiss"
                        aria-label="Close conversation menu"
                        onClick={() => setOpenMenu(null)}
                        type="button"
                      />
                      <div className="itihasa-row-menu">
                        <button onClick={() => { onPin(conversation.id); setOpenMenu(null); }}>
                          <Pin size={14} /> {conversation.pinned ? "Unpin chat" : "Pin chat"}
                        </button>
                        <button onClick={() => { onRename(conversation.id); setOpenMenu(null); }}>
                          <FileText size={14} /> Rename
                        </button>
                        <button className="is-danger" onClick={() => { onDelete(conversation.id); setOpenMenu(null); }}>
                          <Trash2 size={14} /> Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))}
            {filtered.length === 0 && (
              <p className="itihasa-history-empty">
                {savedOnly ? "Saved chats will show up here." : search ? "No matching conversations." : "Your chats will show up here."}
              </p>
            )}
          </div>
        </div>
        <div className="itihasa-sidebar-foot">
          <span className="itihasa-status-dot" />
          <span>Browser-local history</span>
          <span className="itihasa-local-badge">PRIVATE</span>
        </div>
      </aside>
    </>
  );
}

function SourceCard({
  source,
  messageId,
}: {
  source: ChatSource;
  messageId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article
      className={`itihasa-source-card ${expanded ? "is-expanded" : ""}`}
      data-source-card={`${messageId}:${source.id}`}
    >
      <button
        aria-expanded={expanded}
        className="itihasa-source-trigger"
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        <span className="itihasa-source-number">
          {source.id.replace(/^chunk-/, "")}
        </span>
        <span className="itihasa-source-main">
          <strong>{source.title}</strong>
          <small>{source.languageScript} <span>·</span> {source.pageSection}</small>
        </span>
        {source.relevanceScore !== undefined && (
          <span className="itihasa-source-score">
            {source.relevanceScore.toFixed(2)} <small>reranker score</small>
          </span>
        )}
        <ChevronDown size={16} className="itihasa-source-chevron" />
      </button>
      {expanded && (
        <div className="itihasa-source-detail">
          <p>{source.snippet}</p>
          <span>Document {source.documentId}</span>
        </div>
      )}
    </article>
  );
}

function MessageActions({
  message,
  onCopy,
  onRegenerate,
  onSave,
  onSources,
  onFeedback,
  isSaved,
  isLastAssistant,
}: {
  message: ChatMessage;
  onCopy: () => void;
  onRegenerate: () => void;
  onSave: () => void;
  onSources: () => void;
  onFeedback: (value: "up" | "down") => void;
  isSaved: boolean;
  isLastAssistant: boolean;
}) {
  return (
    <div className="itihasa-message-actions">
      <IconButton label="Copy answer" onClick={onCopy}><Copy size={15} /></IconButton>
      {isLastAssistant && (
        <IconButton label="Regenerate answer" onClick={onRegenerate}><LoaderCircle size={15} /></IconButton>
      )}
      <IconButton label={isSaved ? "Remove saved answer" : "Save answer"} onClick={onSave} className={isSaved ? "is-saved" : ""}>
        <Bookmark size={15} />
      </IconButton>
      {message.sources.length > 0 && (
        <IconButton label="View sources" onClick={onSources}><BookOpen size={15} /></IconButton>
      )}
      <span className="itihasa-action-divider" />
      <IconButton label="Helpful" onClick={() => onFeedback("up")} className={message.feedback === "up" ? "is-selected" : ""}>
        <ThumbsUp size={15} />
      </IconButton>
      <IconButton label="Not helpful" onClick={() => onFeedback("down")} className={message.feedback === "down" ? "is-selected" : ""}>
        <ThumbsDown size={15} />
      </IconButton>
    </div>
  );
}

function MessageItem({
  message,
  isLastAssistant,
  isSaved,
  onCopy,
  onRegenerate,
  onSave,
  onSources,
  onFeedback,
  onCitation,
}: {
  message: ChatMessage;
  isLastAssistant: boolean;
  isSaved: boolean;
  onCopy: (content: string) => void;
  onRegenerate: () => void;
  onSave: () => void;
  onSources: () => void;
  onFeedback: (value: "up" | "down") => void;
  onCitation: (messageId: string, sourceId: string) => void;
}) {
  if (message.role === "user") {
    return (
      <article className="itihasa-user-message">
        <div className="itihasa-user-bubble">
          <p>{message.content}</p>
          {message.attachment && (
            <span className="itihasa-attachment-chip">
              <FileText size={14} /> {message.attachment.name}
              <small>{message.attachment.size < 1024 * 1024
                ? `${Math.max(1, Math.round(message.attachment.size / 1024))} KB`
                : `${(message.attachment.size / (1024 * 1024)).toFixed(1)} MB`}</small>
            </span>
          )}
        </div>
        <span className="itihasa-message-time">{formatTime(message.timestamp)}</span>
      </article>
    );
  }

  return (
    <article className="itihasa-assistant-message">
      <div className="itihasa-assistant-heading">
        <span className="itihasa-assistant-avatar"><Sparkles size={15} /></span>
        <strong>Itihasa AI</strong>
        <span className="itihasa-answer-language">Answer in {message.language}</span>
        {message.status !== "completed" &&
          message.status !== "failed" &&
          message.status !== "stopped" && (
          <span className="itihasa-live-status">
            {message.status === "uploading"
              ? "Uploading document"
              : message.status === "indexing"
                ? "Indexing document"
                : "Searching records"}
            <i />
          </span>
        )}
      </div>
      <div className="itihasa-assistant-content">
        {message.content ? (
          <ChatMarkdown content={message.content} onCitationClick={(id) => onCitation(message.id, id)} />
        ) : message.status === "pending" ||
          message.status === "uploading" ||
          message.status === "indexing" ||
          message.status === "querying" ? (
          <div className="itihasa-pipeline-loader" role="status" aria-live="polite">
            <LoaderCircle size={16} />
            <span>{message.progressDetail ?? (
              message.status === "uploading"
                ? "Uploading your document…"
                : message.status === "indexing"
                  ? "Indexing the uploaded document…"
                  : "Searching your indexed sources…"
            )}</span>
          </div>
        ) : message.status === "failed" ? (
          <p className="itihasa-error-message">
            {message.errorDetails ?? "The request could not be completed."}
          </p>
        ) : null}
        {message.status === "stopped" && message.content && (
          <span className="itihasa-stopped-note">Generation stopped</span>
        )}
      </div>
      {message.status === "completed" && (
        <>
          {message.sources.length > 0 && (
            <section className="itihasa-sources" aria-label="Sources">
              <div className="itihasa-sources-heading">
                <span><BookOpen size={15} /> Sources</span>
                <small>Retrieved passages with page citations</small>
              </div>
              {message.sources.map((source) => (
                <SourceCard key={source.id} messageId={message.id} source={source} />
              ))}
            </section>
          )}
          <MessageActions
            isLastAssistant={isLastAssistant}
            isSaved={isSaved}
            message={message}
            onCopy={() => onCopy(message.content)}
            onFeedback={onFeedback}
            onRegenerate={onRegenerate}
            onSave={onSave}
            onSources={onSources}
          />
        </>
      )}
    </article>
  );
}

function LanguageSelect({
  language,
  onChange,
}: {
  language: ResponseLanguage;
  onChange: (language: ResponseLanguage) => void;
}) {
  return (
    <label className="itihasa-select">
      <Globe2 size={15} />
      <select
        aria-label="Response language"
        onChange={(event) => onChange(event.target.value as ResponseLanguage)}
        value={language}
      >
        {responseLanguages.map((item) => <option key={item}>{item}</option>)}
      </select>
      <ChevronDown size={14} />
    </label>
  );
}

function EmptyChat({
  onSuggestion,
}: {
  onSuggestion: (prompt: string) => void;
}) {
  return (
    <div className="itihasa-empty-state">
      <div className="itihasa-empty-mark"><BookOpen size={24} /></div>
      <span className="itihasa-eyebrow">A reading room for the past</span>
      <h1>Explore India&apos;s<br /><em>historical knowledge.</em></h1>
      <p>Ask across languages, scripts, and centuries.<br className="itihasa-desktop-break" /> Follow every answer back to its evidence.</p>
      <div className="itihasa-suggestions">
        <div className="itihasa-suggestions-label"><Sparkles size={14} /> Start with a question</div>
        <div className="itihasa-suggestion-grid">
          {suggestions.map(({ prompt, script }, index) => (
            <button className="itihasa-suggestion" key={prompt} onClick={() => onSuggestion(prompt)}>
              <span className="itihasa-suggestion-index">0{index + 1}</span>
              <span><small>{script}</small><strong>{prompt}</strong></span>
              <ArrowUp size={15} />
            </button>
          ))}
        </div>
      </div>
      <span className="itihasa-demo-disclaimer">
        Answers use uploaded documents and include page-level source citations.
      </span>
    </div>
  );
}

function ChatComposer({
  query,
  setQuery,
  language,
  setLanguage,
  mode,
  setMode,
  attachment,
  setAttachment,
  onFileSelect,
  onSend,
  onStop,
  isGenerating,
  onNotify,
}: {
  query: string;
  setQuery: (query: string) => void;
  language: ResponseLanguage;
  setLanguage: (language: ResponseLanguage) => void;
  mode: RetrievalMode;
  setMode: (mode: RetrievalMode) => void;
  attachment: ChatAttachment | null;
  setAttachment: (attachment: ChatAttachment | null) => void;
  onFileSelect: (file: File | null) => void;
  onSend: () => void;
  onStop: () => void;
  isGenerating: boolean;
  onNotify: (message: string, type?: "success" | "error") => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [query]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      event.keyCode !== 229
    ) {
      event.preventDefault();
      onSend();
    }
  };

  return (
    <div className="itihasa-composer-wrap">
      <div className="itihasa-composer">
        {attachment && (
          <div className="itihasa-pending-attachment">
            <FileText size={15} />
            <span>{attachment.name}</span>
            <IconButton
              label="Remove attachment"
              onClick={() => {
                setAttachment(null);
                onFileSelect(null);
              }}
            >
              <X size={14} />
            </IconButton>
          </div>
        )}
        <textarea
          aria-label="Message Itihasa AI"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about a historical document, event, or idea…"
          ref={textareaRef}
          rows={1}
          value={query}
        />
        <div className="itihasa-composer-toolbar">
          <div className="itihasa-composer-tools">
            <label className="itihasa-attach-button" title="Attach a document">
              <Paperclip size={16} />
              <span>Attach</span>
              <input
                accept={supportedDocumentExtensions.join(",")}
                aria-label="Upload a document with your question"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
                    if (!supportedDocumentExtensions.includes(extension as (typeof supportedDocumentExtensions)[number])) {
                      onNotify("This document type is not supported by the API.", "error");
                      onFileSelect(null);
                      setAttachment(null);
                    } else {
                      setAttachment({ name: file.name, size: file.size, type: file.type });
                      onFileSelect(file);
                    }
                  }
                  event.target.value = "";
                }}
                type="file"
              />
            </label>
            <span className="itihasa-toolbar-separator" />
            <LanguageSelect language={language} onChange={setLanguage} />
            <label className="itihasa-mode-select">
              <Network size={14} />
              <select
                aria-label="Retrieval mode"
                onChange={(event) => setMode(event.target.value as RetrievalMode)}
                value={mode}
              >
                <option value="Hybrid">Hybrid (dense + keyword)</option>
              </select>
              <ChevronDown size={13} />
            </label>
          </div>
          {isGenerating ? (
            <Button className="itihasa-stop-button" onClick={onStop}>
              <PanelLeftClose data-icon="inline-start" /> Stop
            </Button>
          ) : (
            <Button className="itihasa-send-button" disabled={!query.trim()} onClick={onSend} aria-label="Send message">
              <ArrowUp size={18} />
            </Button>
          )}
        </div>
      </div>
      <div className="itihasa-composer-hint">
        <span><kbd>Enter</kbd> to send <i>·</i> <kbd>Shift + Enter</kbd> for a new line</span>
        <span>Answers are grounded in your indexed documents</span>
      </div>
    </div>
  );
}

function ArchiveView({
  documents,
  loading,
  refreshing,
  error,
  onRefresh,
  onUpload,
  onDelete,
}: {
  documents: ApiDocument[];
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  onRefresh: () => void;
  onUpload: (file: File) => Promise<void>;
  onDelete: (document: ApiDocument) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const records = documents.filter((document) =>
    `${document.title} ${document.filename} ${document.language}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );

  const submitUpload = async () => {
    if (!selectedFile || uploading) return;
    setUploading(true);
    setUploadError(null);
    try {
      await onUpload(selectedFile);
      setSelectedFile(null);
    } catch (error) {
      setUploadError(apiErrorMessage(error));
    } finally {
      setUploading(false);
    }
  };

  return (
    <section className="itihasa-secondary-view">
      <span className="itihasa-eyebrow">HISTORICAL ARCHIVE</span>
      <h1>Explore the collection.</h1>
      <p className="itihasa-secondary-intro">Upload and manage the source documents used by historical search.</p>
      <div className="itihasa-archive-upload">
        <label className="itihasa-archive-file">
          <Upload size={16} />
          <span>{selectedFile?.name ?? "Choose a document to upload"}</span>
          <input
            accept={supportedDocumentExtensions.join(",")}
            aria-label="Choose a document to upload"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
        <Button
          className="itihasa-new-chat"
          disabled={!selectedFile || uploading}
          onClick={() => void submitUpload()}
        >
          {uploading ? <LoaderCircle className="itihasa-spin" size={15} /> : <Upload size={15} />}
          {uploading ? "Uploading…" : "Upload"}
        </Button>
        <Button
          className="itihasa-archive-refresh"
          disabled={refreshing}
          onClick={onRefresh}
          title="Refresh document statuses"
        >
          <RefreshCw className={refreshing ? "itihasa-spin" : ""} size={15} />
          Refresh
        </Button>
      </div>
      <label className="itihasa-archive-search"><Search size={16} /><input aria-label="Search records" onChange={(event) => setSearch(event.target.value)} placeholder="Search titles or languages" value={search} /></label>
      {error && (
        <div className="itihasa-api-error" role="alert">
          <span>{error}</span>
          <button onClick={onRefresh} type="button">Retry</button>
        </div>
      )}
      {uploadError && <p className="itihasa-api-error" role="alert">{uploadError}</p>}
      <div className="itihasa-archive-grid">
        {loading ? (
          <p className="itihasa-history-empty" role="status">Loading documents…</p>
        ) : records.map((record) => (
          <article className="itihasa-archive-card" key={record.id}>
            <span className="itihasa-source-icon"><FileText size={18} /></span>
            <span className={`itihasa-document-status is-${record.status}`}>
              {record.status}
            </span>
            <h2>{record.title}</h2>
            <p>{record.filename} · {record.language}</p>
            <small>
              {record.status === "indexed"
                ? `${record.num_chunks.toLocaleString()} chunks · ${record.num_pages.toLocaleString()} pages`
                : record.error ?? record.progress_detail ?? `${record.progress_percent}% complete`}
            </small>
            {record.status !== "indexed" && record.status !== "failed" && (
              <div
                aria-label={`Ingestion ${record.progress_percent}% complete`}
                className="itihasa-document-progress"
              >
                <span style={{ width: `${record.progress_percent}%` }} />
              </div>
            )}
            <button
              aria-label={`Delete ${record.title}`}
              className="itihasa-document-delete"
              onClick={() => void onDelete(record)}
              type="button"
            >
              <Trash2 size={14} /> Delete
            </button>
          </article>
        ))}
        {!loading && !error && records.length === 0 && (
          <p className="itihasa-history-empty">
            {search
              ? "No documents match this search."
              : "No documents yet. Upload a source to start searching."}
          </p>
        )}
      </div>
    </section>
  );
}

function ResearchView({
  health,
  documents,
  loading,
  error,
  onRetry,
}: {
  health: ApiHealth | null;
  documents: ApiDocument[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const indexed = documents.filter((document) => document.status === "indexed").length;
  return (
    <section className="itihasa-secondary-view">
      <span className="itihasa-eyebrow">RESEARCH DASHBOARD</span>
      <h1>Research, with context.</h1>
      <p className="itihasa-secondary-intro">Live ingestion and retrieval health from the Itihasa API.</p>
      {error && <div className="itihasa-api-error" role="alert"><span>{error}</span><button onClick={onRetry} type="button">Retry</button></div>}
      <div className="itihasa-dashboard-grid">
        <article><span>DOCUMENTS</span><strong>{loading ? "…" : documents.length.toLocaleString()}</strong><p>{indexed.toLocaleString()} indexed and ready for retrieval.</p></article>
        <article><span>INDEXED CHUNKS</span><strong>{loading || !health ? "…" : health.sparse_docs.toLocaleString()}</strong><p>Dense vectors: {loading || !health ? "…" : health.dense_vectors.toLocaleString()}.</p></article>
        <article><span>RETRIEVAL</span><strong>{health?.status === "ok" ? "Online" : loading ? "Checking" : "Unavailable"}</strong><p>Hybrid dense and keyword search.</p></article>
      </div>
      <div className="itihasa-honesty-card"><CircleHelp size={18} /><p>Conversation history and saved-chat controls are stored in this browser; the backend currently provides no account or conversation-sync endpoints.</p></div>
    </section>
  );
}

function SettingsView({ onClear }: { onClear: () => void }) {
  return (
    <section className="itihasa-secondary-view">
      <span className="itihasa-eyebrow">SETTINGS</span>
      <h1>Your workspace.</h1>
      <p className="itihasa-secondary-intro">Conversation history and saved-chat preferences are stored locally in this browser.</p>
      <div className="itihasa-settings-card">
        <div><strong>Clear local chat history</strong><p>Remove all conversations saved in this browser. This cannot be undone.</p></div>
        <Button className="itihasa-clear-button" onClick={onClear}>Clear history</Button>
      </div>
      <div className="itihasa-honesty-card"><CircleHelp size={18} /><p>Documents attached to a question are uploaded to the backend and indexed before that question is searched. Chat history remains local to this browser.</p></div>
    </section>
  );
}

export default function WorkspacePage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<WorkspaceView>("chat");
  const [language, setLanguage] = useState<ResponseLanguage>("English");
  const [mode, setMode] = useState<RetrievalMode>("Hybrid");
  const [query, setQuery] = useState("");
  const [attachment, setAttachment] = useState<ChatAttachment | null>(null);
  const [attachmentFile, setAttachmentFile] = useState<File | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [documents, setDocuments] = useState<ApiDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const shouldPinToBottom = useRef(true);
  const activeGeneration = useRef<{
    conversationId: string;
    messageId: string;
    controller: AbortController;
  } | null>(null);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed: unknown = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          const containsDemoSources = parsed.some(
            (conversation) =>
              typeof conversation === "object" &&
              conversation !== null &&
              "messages" in conversation &&
              Array.isArray(conversation.messages) &&
              conversation.messages.some(
                (message: unknown) =>
                  typeof message === "object" &&
                  message !== null &&
                  "sources" in message &&
                  Array.isArray(message.sources) &&
                  message.sources.some(
                    (source: unknown) =>
                      typeof source === "object" &&
                      source !== null &&
                      "isIllustrative" in source &&
                      source.isIllustrative === true,
                  ),
              ),
          );
          if (containsDemoSources) {
            window.localStorage.removeItem(STORAGE_KEY);
            setToast({
              message: "Old demonstration chats were cleared; new answers use live sources.",
              type: "success",
            });
          } else {
            setConversations(parsed as Conversation[]);
          }
        } else {
          console.error("Stored chat history has an invalid format.");
          setToast({ message: "Saved chat history could not be read.", type: "error" });
        }
      }
    } catch (error) {
      console.error("Could not read saved chat history.", error);
      setToast({ message: "Saved chat history could not be read.", type: "error" });
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (!loaded) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch (error) {
      console.error("Could not save chat history.", error);
      setToast({ message: "Chat history could not be saved in this browser.", type: "error" });
    }
  }, [conversations, loaded]);

  useEffect(() => {
    return () => activeGeneration.current?.controller.abort();
  }, []);

  const refreshDocuments = useCallback(async () => {
    setDocumentsLoading(true);
    setDocumentsError(null);
    try {
      setDocuments(await api.listDocuments());
    } catch (error) {
      setDocumentsError(apiErrorMessage(error));
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    setHealthError(null);
    try {
      setHealth(await api.health());
    } catch (error) {
      setHealthError(apiErrorMessage(error));
    }
  }, []);

  useEffect(() => {
    void refreshDocuments();
    void refreshHealth();
  }, [refreshDocuments, refreshHealth]);

  const showToast = useCallback((message: string, type: "success" | "error" = "success") => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 2600);
  }, []);

  const selectedConversation = conversations.find((conversation) => conversation.id === selectedId) ?? null;
  const messages = selectedConversation?.messages ?? [];
  const isGenerating = activeGeneration.current?.conversationId === selectedId;

  useEffect(() => {
    if (!shouldPinToBottom.current) return;
    const thread = threadRef.current;
    if (thread) thread.scrollTo({ top: thread.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const updateMessage = useCallback(
    (conversationId: string, messageId: string, update: (message: ChatMessage) => ChatMessage) => {
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id !== conversationId
            ? conversation
            : {
                ...conversation,
                timestamp: Date.now(),
                messages: conversation.messages.map((message) =>
                  message.id === messageId ? update(message) : message,
                ),
              },
        ),
      );
    },
    [],
  );

  const executeQuery = useCallback(
    async (
      conversationId: string,
      messageId: string,
      question: string,
      answerLanguage: ResponseLanguage,
      file?: File,
    ) => {
      const controller = new AbortController();
      activeGeneration.current?.controller.abort();
      activeGeneration.current = { conversationId, messageId, controller };
      let uploadedDocument: ApiDocument | undefined;
      try {
        if (file) {
          updateMessage(conversationId, messageId, (message) => ({
            ...message,
            status: "uploading",
            progressDetail: `Uploading ${file.name}…`,
          }));
          const uploaded = await api.uploadDocument(file, {
            language: answerLanguage,
            signal: controller.signal,
          });
          uploadedDocument = uploaded;
          setDocuments((current) => [
            uploaded,
            ...current.filter((document) => document.id !== uploaded.id),
          ]);
          if (uploaded.status === "failed") {
            throw new Error(uploaded.error ?? "The uploaded document could not be processed.");
          }

          let currentDocument = uploaded;
          while (currentDocument.status !== "indexed") {
            updateMessage(conversationId, messageId, (message) => ({
              ...message,
              status: "indexing",
              progressDetail:
                currentDocument.progress_detail ??
                `Indexing ${currentDocument.progress_percent}% complete…`,
            }));
            await waitForDelay(2000, controller.signal);
            currentDocument = await api.getDocument(uploaded.id, controller.signal);
            setDocuments((current) =>
              current.map((document) =>
                document.id === currentDocument.id ? currentDocument : document,
              ),
            );
            if (currentDocument.status === "failed") {
              throw new Error(
                currentDocument.error ?? "The uploaded document could not be indexed.",
              );
            }
          }
        }

        updateMessage(conversationId, messageId, (message) => ({
          ...message,
          status: "querying",
          progressDetail: "Searching indexed sources…",
        }));
        const result: QueryResponse = await api.query(
          { question, answer_language: answerLanguage },
          controller.signal,
        );
        const rerankScores = new Map(
          result.retrieval.reranked.map((hit) => [hit.chunk_id, hit.score]),
        );
        const documentLanguages = new Map(
          [...documents, ...(uploadedDocument ? [uploadedDocument] : [])].map(
            (document) => [document.id, document.language] as const,
          ),
        );
        const sources: ChatSource[] = result.citations.map((citation) => ({
          id: `chunk-${citation.chunk_db_id}`,
          documentId: citation.document_id,
          title: citation.title,
          languageScript: documentLanguages.get(citation.document_id) ?? "Unknown language",
          pageSection:
            citation.page_start === citation.page_end
              ? `Page ${citation.page_start}`
              : `Pages ${citation.page_start}–${citation.page_end}`,
          snippet: citation.excerpt,
          relevanceScore: rerankScores.get(citation.chunk_db_id),
        }));
        updateMessage(conversationId, messageId, (message) => ({
          ...message,
          content: result.answer,
          sources,
          status: "completed",
          errorDetails: undefined,
          progressDetail: undefined,
        }));
      } catch (error) {
        if (!controller.signal.aborted) {
          updateMessage(conversationId, messageId, (message) => ({
            ...message,
            status: "failed",
            errorDetails: apiErrorMessage(error),
            progressDetail: undefined,
          }));
        }
      } finally {
        if (activeGeneration.current?.controller === controller) {
          activeGeneration.current = null;
        }
      }
    },
    [documents, updateMessage],
  );

  const sendMessage = useCallback(() => {
    const text = query.trim();
    if (!text || activeGeneration.current) return;
    const now = Date.now();
    const conversationId = selectedId ?? makeId();
    const userMessage: ChatMessage = {
      id: makeId(),
      conversationId,
      role: "user",
      content: text,
      timestamp: now,
      status: "completed",
      sources: [],
      language,
      attachment: attachment ?? undefined,
    };
    const assistantId = makeId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      conversationId,
      role: "assistant",
      content: "",
      timestamp: now + 1,
      status: attachmentFile ? "uploading" : "querying",
      sources: [],
      language,
    };
    setConversations((current) => {
      const existing = current.find((conversation) => conversation.id === conversationId);
      if (existing) {
        return current.map((conversation) =>
          conversation.id === conversationId
            ? { ...conversation, timestamp: now, messages: [...conversation.messages, userMessage, assistantMessage] }
            : conversation,
        );
      }
      return [
        {
          id: conversationId,
          title: conversationTitle(text),
          pinned: false,
          saved: false,
          timestamp: now,
          messages: [userMessage, assistantMessage],
        },
        ...current,
      ];
    });
    setSelectedId(conversationId);
    setView("chat");
    setQuery("");
    setAttachment(null);
    setAttachmentFile(null);
    shouldPinToBottom.current = true;
    void executeQuery(conversationId, assistantId, text, language, attachmentFile ?? undefined);
  }, [attachment, attachmentFile, executeQuery, language, query, selectedId]);

  const stopGeneration = () => {
    const active = activeGeneration.current;
    if (!active) return;
    active.controller.abort();
    updateMessage(active.conversationId, active.messageId, (message) => ({
      ...message,
      status: "stopped",
    }));
    activeGeneration.current = null;
    showToast("Stopped waiting for the response. Uploaded documents may continue indexing.");
  };

  const newChat = () => {
    if (activeGeneration.current) stopGeneration();
    setSelectedId(null);
    setView("chat");
    setQuery("");
    setAttachment(null);
    setAttachmentFile(null);
    setMobileOpen(false);
    shouldPinToBottom.current = true;
  };

  const selectChat = (id: string) => {
    if (activeGeneration.current?.conversationId === selectedId && selectedId !== id) stopGeneration();
    setSelectedId(id);
    setView("chat");
    shouldPinToBottom.current = true;
  };

  const selectView = (nextView: WorkspaceView) => {
    setView(nextView);
    setMobileOpen(false);
  };

  const togglePinned = (id: string) => {
    setConversations((current) => current.map((conversation) =>
      conversation.id === id ? { ...conversation, pinned: !conversation.pinned } : conversation,
    ));
    showToast("Conversation pin updated.");
  };

  const renameConversation = (id: string) => {
    const conversation = conversations.find((item) => item.id === id);
    if (!conversation) return;
    const nextTitle = window.prompt("Rename conversation", conversation.title)?.trim();
    if (!nextTitle) return;
    setConversations((current) => current.map((item) =>
      item.id === id ? { ...item, title: nextTitle.slice(0, 80) } : item,
    ));
    showToast("Conversation renamed.");
  };

  const deleteConversation = (id: string) => {
    const conversation = conversations.find((item) => item.id === id);
    if (!conversation || !window.confirm(`Delete "${conversation.title}"?`)) return;
    if (activeGeneration.current?.conversationId === id) stopGeneration();
    setConversations((current) => current.filter((item) => item.id !== id));
    if (selectedId === id) setSelectedId(null);
    showToast("Conversation deleted.");
  };

  const clearHistory = () => {
    if (!conversations.length) {
      showToast("There are no conversations to clear.");
      return;
    }
    if (!window.confirm("Delete all conversations saved in this browser?")) return;
    if (activeGeneration.current) stopGeneration();
    setConversations([]);
    setSelectedId(null);
    showToast("Local chat history cleared.");
  };

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast("Copied to clipboard.");
    } catch (error) {
      console.error("Clipboard access failed.", error);
      showToast("Could not access the clipboard.", "error");
    }
  };

  const saveAnswer = () => {
    if (!selectedId) return;
    const saved = !selectedConversation?.saved;
    setConversations((current) => current.map((conversation) =>
      conversation.id === selectedId ? { ...conversation, saved } : conversation,
    ));
    showToast(saved ? "Conversation saved." : "Conversation removed from saved.");
  };

  const regenerate = (message: ChatMessage) => {
    if (!selectedId || activeGeneration.current) return;
    const messageIndex = selectedConversation?.messages.findIndex(
      (item) => item.id === message.id,
    ) ?? -1;
    const previousUserMessage = selectedConversation?.messages
      .slice(0, messageIndex)
      .findLast((item) => item.role === "user");
    if (!previousUserMessage) {
      showToast("The original question could not be found.", "error");
      return;
    }
    updateMessage(selectedId, message.id, (current) => ({
      ...current,
      content: "",
      status: "querying",
      sources: [],
      errorDetails: undefined,
    }));
    shouldPinToBottom.current = true;
    void executeQuery(
      selectedId,
      message.id,
      previousUserMessage.content,
      message.language,
    );
  };

  const feedback = (messageId: string, value: "up" | "down") => {
    if (!selectedId) return;
    updateMessage(selectedId, messageId, (message) => ({
      ...message,
      feedback: message.feedback === value ? undefined : value,
    }));
    showToast("Thanks for your feedback.");
  };

  const viewSources = (messageId: string) => {
    document.querySelector(`[data-source-card^="${messageId}:"]`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  };

  const openCitation = (messageId: string, sourceId: string) => {
    const target = document.querySelector(`[data-source-card="${messageId}:${sourceId}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    target?.classList.add("is-highlighted");
    window.setTimeout(() => target?.classList.remove("is-highlighted"), 1500);
  };

  const uploadArchiveDocument = async (file: File) => {
    try {
      const uploaded = await api.uploadDocument(file);
      setDocuments((current) => [
        uploaded,
        ...current.filter((document) => document.id !== uploaded.id),
      ]);
      showToast(`Uploaded ${uploaded.title}. Refresh to check indexing progress.`);
    } catch (error) {
      showToast(apiErrorMessage(error), "error");
      throw error;
    }
  };

  const deleteArchiveDocument = async (document: ApiDocument) => {
    if (!window.confirm(`Delete "${document.title}" and its indexed chunks?`)) return;
    try {
      await api.deleteDocument(document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      showToast(`Deleted ${document.title}.`);
    } catch (error) {
      showToast(apiErrorMessage(error), "error");
    }
  };

  const lastAssistantId = [...messages].reverse().find((message) => message.role === "assistant")?.id;

  return (
    <div className="itihasa-app-shell">
      <Sidebar
        conversations={conversations}
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        onDelete={deleteConversation}
        onNewChat={newChat}
        onPin={togglePinned}
        onRename={renameConversation}
        onSelectChat={selectChat}
        onSelectView={selectView}
        selectedId={selectedId}
        view={view}
      />
      <main className="itihasa-main">
        <header className="itihasa-header">
          <div className="itihasa-header-title">
            <IconButton label="Open navigation" className="itihasa-menu-open" onClick={() => setMobileOpen(true)}>
              <Menu size={19} />
            </IconButton>
            <span className="itihasa-breadcrumb">Itihasa <span>/</span></span>
            <strong>{view === "chat" ? selectedConversation?.title ?? "New conversation" : view === "archive" ? "Historical archive" : view === "research" ? "Research dashboard" : "Settings"}</strong>
          </div>
          {view === "chat" ? (
            <div className="itihasa-header-actions">
              <LanguageSelect language={language} onChange={setLanguage} />
              <IconButton label="Start a new chat" onClick={newChat}><MessageSquarePlus size={17} /></IconButton>
            </div>
          ) : (
            <IconButton label="Back to chat" onClick={newChat}><MessageSquarePlus size={17} /></IconButton>
          )}
        </header>

        {view === "chat" ? (
          <div className="itihasa-chat-layout">
            <div
              className={`itihasa-thread ${messages.length ? "has-messages" : "is-empty"}`}
              onScroll={(event) => {
                const element = event.currentTarget;
                shouldPinToBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 70;
              }}
              ref={threadRef}
            >
              {!messages.length ? (
                <EmptyChat onSuggestion={setQuery} />
              ) : (
                <div className="itihasa-message-list">
                  {messages.map((message) => (
                    <MessageItem
                      isLastAssistant={message.id === lastAssistantId}
                      isSaved={Boolean(selectedConversation?.saved)}
                      key={message.id}
                      message={message}
                      onCitation={openCitation}
                      onCopy={copyText}
                      onFeedback={(value) => feedback(message.id, value)}
                      onRegenerate={() => regenerate(message)}
                      onSave={saveAnswer}
                      onSources={() => viewSources(message.id)}
                    />
                  ))}
                </div>
              )}
            </div>
            <ChatComposer
              attachment={attachment}
              isGenerating={Boolean(isGenerating)}
              language={language}
              mode={mode}
              onNotify={showToast}
              onFileSelect={setAttachmentFile}
              onSend={sendMessage}
              onStop={stopGeneration}
              query={query}
              setAttachment={setAttachment}
              setLanguage={setLanguage}
              setMode={setMode}
              setQuery={setQuery}
            />
          </div>
        ) : view === "archive" ? (
          <ArchiveView
            documents={documents}
            error={documentsError}
            loading={documentsLoading}
            onDelete={deleteArchiveDocument}
            onRefresh={() => void refreshDocuments()}
            onUpload={uploadArchiveDocument}
            refreshing={documentsLoading}
          />
        ) : view === "research" ? (
          <ResearchView
            documents={documents}
            error={documentsError ?? healthError}
            health={health}
            loading={documentsLoading}
            onRetry={() => {
              void refreshDocuments();
              void refreshHealth();
            }}
          />
        ) : (
          <SettingsView onClear={clearHistory} />
        )}
      </main>
      {toast && (
        <div className={`itihasa-toast ${toast.type}`} role="status" aria-live="polite">
          {toast.type === "success" ? <Check size={16} /> : <CircleHelp size={16} />}
          {toast.message}
        </div>
      )}
    </div>
  );
}
