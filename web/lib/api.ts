/** All API requests live here. Report types are generated from the API contract. */
import type { components } from "./api.gen";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");
export type Report = components["schemas"]["ReportResponse"];
export type ReportBody = components["schemas"]["ReportBody"];
export type ReportSummary = components["schemas"]["ReportSummary"];
export type CreatedReport = components["schemas"]["CreateReportResponse"];
export type QuotaError = components["schemas"]["QuotaError"];
export type DuplicateError = components["schemas"]["DuplicateError"];
export type ReportStatus = Report["status"];
export const TERMINAL: ReportStatus[] = ["succeeded", "failed"];
export const ANON_KEY = "ideacheck-anon-id";
// These two endpoints currently expose unstructured dictionaries in OpenAPI.
export type CorpusStats = Record<
  "ideas" | "entities" | "research_chunks",
  { total: number; embedded: number }
>;
export type Credentials = { token?: string | null; signal?: AbortSignal };

function anonId(): string {
  let id = localStorage.getItem(ANON_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(ANON_KEY, id);
  }
  return id;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(explain(status, body));
    this.name = "ApiError";
  }
  get reason(): QuotaError["reason"] | DuplicateError["reason"] | undefined {
    return (this.body as QuotaError | DuplicateError | null)?.reason;
  }
  get existingSlug(): string | undefined {
    return (this.body as DuplicateError | null)?.existing_slug;
  }
}
function explain(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(". ");
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 404)
    return "We couldn’t find that report. Check the link and try again.";
  return "We couldn’t complete this request. Please try again.";
}
export function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "We couldn’t reach the research service. Please try again shortly.";
}
async function request<T>(
  path: string,
  init: RequestInit = {},
  credentials?: Credentials,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (credentials) {
    headers.set("X-Anon-Id", anonId());
    if (credentials.token)
      headers.set("Authorization", `Bearer ${credentials.token}`);
  }
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    signal: credentials?.signal ?? init.signal,
    cache: "no-store",
  });
  if (!res.ok)
    throw new ApiError(res.status, await res.json().catch(() => null));
  return res.json() as Promise<T>;
}
export function createReport(
  idea: string,
  targetUser?: string,
  force = false,
  credentials: Credentials = {},
) {
  return request<CreatedReport>(
    "/reports",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ idea, target_user: targetUser || null, force }),
    },
    credentials,
  );
}
export function getReport(slug: string, signal?: AbortSignal) {
  return request<Report>(`/reports/${encodeURIComponent(slug)}`, { signal });
}
export function listReports(credentials: Credentials = {}, limit = 100) {
  return request<ReportSummary[]>(`/reports?limit=${limit}`, {}, credentials);
}
export function claimReports(credentials: Credentials) {
  return request<{ claimed: number }>(
    "/auth/claim",
    { method: "POST" },
    credentials,
  );
}
export function getCorpusStats(signal?: AbortSignal) {
  return request<CorpusStats>("/corpus/stats", { signal });
}
export function getHealth(signal?: AbortSignal) {
  return request<{ status: string }>("/health", { signal });
}
export function safeUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
