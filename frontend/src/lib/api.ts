import { SSEParser } from "./sse";
import type { AskEvent, Collection, InviteCreated, NoteDocument, Quiz, User } from "./types";

/** Paths are same-origin; next.config.ts forwards them to the FastAPI backend. */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly retryAfterSeconds?: number,
  ) {
    super(message);
  }
}

export async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      // FastAPI validation errors: [{loc, msg, type}]
      return body.detail.map((e: { msg: string }) => e.msg.replace(/^Value error, /, "")).join(". ");
    }
  } catch {
    // not JSON
  }
  return `Request failed (${response.status})`;
}

// One refresh at a time per tab: parallel refreshes would present the same refresh token
// twice, which the backend treats as token theft and answers by revoking the session.
let refreshing: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  refreshing ??= fetch("/auth/refresh", { method: "POST", cache: "no-store" })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function request(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const response = await fetch(path, { ...init, cache: "no-store" });
  if (response.status === 401 && retry && !path.startsWith("/auth/")) {
    if (await refreshSession()) return request(path, init, false);
  }
  if (!response.ok) {
    const retryAfter = Number(response.headers.get("Retry-After")) || undefined;
    throw new ApiError(response.status, await errorMessage(response), retryAfter);
  }
  return response;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return (await request(path, init)).json() as Promise<T>;
}

function sendJson(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

// --- auth & account -----------------------------------------------------------------------

/** Bot-check fields the backend expects from its own forms (backend/app/security/bot.py). */
export interface HumanCheck {
  form_token: string | null;
  website: string; // honeypot: always empty for people
  captcha_token: string | null;
}

export const getFormToken = () => json<{ token: string }>("/auth/form-token").then((r) => r.token);

export const signup = (email: string, password: string, human: HumanCheck) =>
  json<User>("/auth/signup", sendJson("POST", { email, password, ...human }));

export const login = (email: string, password: string, human: HumanCheck) =>
  json<User>("/auth/login", sendJson("POST", { email, password, ...human }));

export const logout = () => request("/auth/logout", { method: "POST" });

export const getMe = () => json<User>("/me");

export const deleteAccount = (password: string) =>
  request("/me", sendJson("DELETE", { password }));

export const exportData = () => json<unknown>("/me/export");

// --- collections ---------------------------------------------------------------------------

export const listCollections = () => json<Collection[]>("/collections");

export const getCollection = (id: string) => json<Collection>(`/collections/${id}`);

export const createCollection = (name: string) =>
  json<Collection>("/collections", sendJson("POST", { name }));

export const deleteCollection = (id: string) =>
  request(`/collections/${id}`, { method: "DELETE" });

export const createInvite = (collectionId: string, expiresInDays = 7) =>
  json<InviteCreated>(
    `/collections/${collectionId}/invites`,
    sendJson("POST", { expires_in_days: expiresInDays }),
  );

export const acceptInvite = (token: string) =>
  json<Collection>("/invites/accept", sendJson("POST", { token }));

// --- documents -----------------------------------------------------------------------------

export const listDocuments = (collectionId: string) =>
  json<NoteDocument[]>(`/collections/${collectionId}/documents`);

/** Raw body, not multipart: the backend counts bytes as they stream in (see documents.py). */
export const uploadDocument = (collectionId: string, file: File) =>
  json<NoteDocument>(
    `/collections/${collectionId}/documents?filename=${encodeURIComponent(file.name)}`,
    { method: "POST", body: file },
  );

export const deleteDocument = (collectionId: string, documentId: string) =>
  request(`/collections/${collectionId}/documents/${documentId}`, { method: "DELETE" });

export const documentFileUrl = (collectionId: string, documentId: string) =>
  `/collections/${collectionId}/documents/${documentId}/file`;

// --- asking --------------------------------------------------------------------------------

/**
 * Stream an answer. Budget (429) and availability (503) problems throw ApiError before any
 * event; failures after the answer starts arrive as an `error` event.
 */
export async function ask(
  collectionId: string,
  question: string,
  onEvent: (event: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await request(`/collections/${collectionId}/ask`, {
    ...sendJson("POST", { question }),
    signal,
  });
  if (!response.body) throw new ApiError(500, "The answer stream could not be opened.");
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const parser = new SSEParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const event of parser.push(value)) onEvent(event);
  }
}

// --- quizzes -------------------------------------------------------------------------------

export const createQuiz = (collectionId: string, numQuestions: number, topic?: string) =>
  json<Quiz>(
    `/collections/${collectionId}/quiz`,
    sendJson("POST", { num_questions: numQuestions, topic: topic || null }),
  );

// --- admin ---------------------------------------------------------------------------------

export interface Analytics {
  days: number;
  total_views: number;
  per_day: { day: string; views: number }[];
  top_pages: { key: string; views: number }[];
  referrers: { key: string | null; views: number }[];
  devices: { key: string; views: number }[];
}

export interface AuditEntry {
  id: number;
  at: string;
  actor: string;
  action: string;
  target: string | null;
  details: Record<string, unknown>;
}

export const getAnalytics = (days = 30) => json<Analytics>(`/admin/analytics?days=${days}`);
export const getAuditLog = (limit = 100) => json<AuditEntry[]>(`/admin/audit-log?limit=${limit}`);
