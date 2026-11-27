export type DocumentStatus =
  | "pending"
  | "extracting"
  | "chunking"
  | "embedding"
  | "indexing"
  | "indexed"
  | "failed";

export type ApiDocument = {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  language: string;
  historical_period: string | null;
  source_url: string | null;
  status: DocumentStatus;
  progress_percent: number;
  progress_detail: string | null;
  error: string | null;
  num_pages: number;
  num_chunks: number;
  created_at: string;
};

export type QueryRequest = {
  question: string;
  answer_language?: string;
};

export type QueryCitation = {
  chunk_db_id: number;
  document_id: string;
  title: string;
  page_start: number;
  page_end: number;
  excerpt: string;
};

export type RetrievalHit = {
  chunk_id: number;
  score: number;
};

export type QueryResponse = {
  answer: string;
  citations: QueryCitation[];
  used_chunk_ids: number[];
  retrieval: {
    dense_hits: number[];
    sparse_hits: number[];
    fused: RetrievalHit[];
    reranked: RetrievalHit[];
    chunk_ids: number[];
  };
};

export type ApiHealth = {
  status: string;
  dense_vectors: number;
  sparse_docs: number;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_ITIHASA_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");
const ACCESS_TOKEN_KEY = "itihasa_access_token";

function accessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = accessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      `Could not connect to the Itihasa API at ${API_BASE_URL}. Check that the backend is running and CORS allows this site.`,
      0,
    );
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body: unknown = await response.json();
      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body
      ) {
        const detail = body.detail;
        message =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail
                  .map((item) =>
                    typeof item === "object" &&
                    item !== null &&
                    "msg" in item &&
                    typeof item.msg === "string"
                      ? item.msg
                      : "Invalid request",
                  )
                  .join("; ")
              : message;
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listDocuments(signal?: AbortSignal): Promise<ApiDocument[]> {
    return request("/api/documents", { signal });
  },

  getDocument(documentId: string, signal?: AbortSignal): Promise<ApiDocument> {
    return request(`/api/documents/${encodeURIComponent(documentId)}`, { signal });
  },

  uploadDocument(
    file: File,
    options: {
      title?: string;
      language?: string;
      historicalPeriod?: string;
      sourceUrl?: string;
      signal?: AbortSignal;
    } = {},
  ): Promise<ApiDocument> {
    const form = new FormData();
    form.set("file", file);
    if (options.title) form.set("title", options.title);
    if (options.language) form.set("language", options.language);
    if (options.historicalPeriod) {
      form.set("historical_period", options.historicalPeriod);
    }
    if (options.sourceUrl) form.set("source_url", options.sourceUrl);
    return request("/api/documents/upload", {
      method: "POST",
      body: form,
      signal: options.signal,
    });
  },

  deleteDocument(documentId: string, signal?: AbortSignal): Promise<void> {
    return request(`/api/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
      signal,
    });
  },

  query(payload: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> {
    return request("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  },

  health(signal?: AbortSignal): Promise<ApiHealth> {
    return request("/health", { signal });
  },
};

export const supportedDocumentExtensions = [
  ".pdf",
  ".png",
  ".jpg",
  ".jpeg",
  ".tiff",
  ".tif",
  ".bmp",
  ".txt",
  ".md",
  ".docx",
  ".epub",
  ".csv",
] as const;
