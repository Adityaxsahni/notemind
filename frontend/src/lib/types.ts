// Mirrors backend/app/schemas.py and the /ask event stream.

export type Role = "owner" | "viewer";

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface Collection {
  id: string;
  name: string;
  role: Role;
  created_at: string;
}

export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

export interface NoteDocument {
  id: string;
  filename: string;
  kind: "pdf" | "docx" | "pptx";
  size_bytes: number;
  status: DocumentStatus;
  progress: number;
  page_count: number | null;
  error: string | null;
  created_at: string;
}

export interface InviteCreated {
  id: string;
  token: string;
  expires_at: string;
}

export interface Citation {
  id: string; // "S1"
  chunk_id: string;
  document_id: string;
  document_title: string;
  page: number;
  heading: string | null;
}

export interface AnswerDone {
  answer: string;
  citations: Citation[];
  grounded: boolean;
  cached: boolean;
  truncated: boolean;
}

export type AskEvent =
  | { type: "token"; text: string }
  | { type: "done"; data: AnswerDone }
  | { type: "error"; message: string };

export interface QuizQuestion {
  question: string;
  options: string[];
  answer: number; // index into options
  explanation: string;
  citation: Citation;
}

export interface Quiz {
  questions: QuizQuestion[];
  found: boolean; // false when the notes don't cover the requested topic
}
