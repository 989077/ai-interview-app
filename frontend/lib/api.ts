// Talks to the FastAPI backend. Change NEXT_PUBLIC_API_URL if the API runs elsewhere.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Question = {
  number: number;
  question: string;
  topic: string;
  difficulty: string;
  is_follow_up: boolean;
};

export type Session = {
  session_id: string;
  status: "in_progress" | "finished";
  n_questions: number;
  answered: number;
  question: Question | null;
};

export type Feedback = {
  score: number;
  correctness: number;
  clarity: number;
  depth: number;
  topic: string;
  strengths: string;
  improve: string;
  better_answer: string;
};

export type AnswerResult = {
  feedback: Feedback;
  answered: number;
  finished: boolean;
  next_question: Question | null;
};

export type Turn = {
  question: string;
  topic: string;
  is_follow_up: boolean;
  answer: string;
  score: number;
  strengths: string;
  improve: string;
  better_answer: string;
};

export type Report = {
  overall_score: number;
  summary: string;
  strengths: string[];
  weak_topics: string[];
  next_practice: string[];
  turns: Turn[];
};

export type HistoryItem = {
  id: string;
  created_at: string;
  role: string;
  level: string;
  n_questions: number;
  answered: number;
  status: "in_progress" | "finished";
  overall_score: number | null;
};

export type StartOptions = {
  level: string;
  n_questions: number;
  topic: string | null;
  resume_text: string;
  job_description: string;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${BASE}. Is uvicorn running?`);
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) message = body.detail[0].msg;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const startSession = (opts: StartOptions) =>
  request<Session>("/sessions", { method: "POST", body: JSON.stringify(opts) });

export const submitAnswer = (id: string, answer: string) =>
  request<AnswerResult>(`/sessions/${id}/answer`, {
    method: "POST",
    body: JSON.stringify({ answer }),
  });

export const getReport = (id: string) => request<Report>(`/sessions/${id}/report`);

export const getHistory = () => request<HistoryItem[]>("/sessions?limit=100");

export const deleteSession = (id: string) => request<void>(`/sessions/${id}`, { method: "DELETE" });
