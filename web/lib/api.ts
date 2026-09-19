/**
 * All API access goes through here.
 *
 * Types come from `api.gen.ts`, generated from the backend's OpenAPI spec by
 * `make types` — do not hand-write shapes that the spec already describes.
 * The fetch helpers stay hand-written on purpose: the interesting part is the
 * credential headers, and burying those in a generated client's middleware
 * would make the one thing worth reading the one thing hardest to find.
 */

import type { components } from "./api.gen";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Report = components["schemas"]["ReportResponse"];
export type ReportBody = components["schemas"]["ReportBody"];
export type ReportSummary = components["schemas"]["ReportSummary"];
export type CreatedReport = components["schemas"]["CreateReportResponse"];
export type QuotaError = components["schemas"]["QuotaError"];
export type DuplicateError = components["schemas"]["DuplicateError"];
export type ReportStatus = Report["status"];

export const TERMINAL: ReportStatus[] = ["succeeded", "failed"];

const ANON_KEY = "ideacheck-anon-id";

/** The anonymous visitor's id, minted once per browser.
 *
 * A dedupe key, not a ceiling — the server pairs it with a per-IP cap, because
 * this header is trivially forgeable. Bearer tokens arrive in Slice 3 with
 * Clerk; until then every caller is anonymous and gets one free run. */
function anonId(): string {
  let id = localStorage.getItem(ANON_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(ANON_KEY, id);
  }
  return id;
}

/** A non-2xx response, with the parsed body kept.
 *
 * The submission gates are the branches the UI actually cares about — "sign in
 * to keep going" vs "out of runs this month" vs "you already ran this" — and
 * they all arrive as errors. Throwing away the body would leave the UI with a
 * status code and no way to tell them apart. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(explain(status, body));
    this.name = "ApiError";
  }

  /** The gate that rejected this submission, if it was one. */
  get reason(): QuotaError["reason"] | DuplicateError["reason"] | undefined {
    const body = this.body as { reason?: string } | null;
    return body?.reason as QuotaError["reason"] | DuplicateError["reason"] | undefined;
  }

  get existingSlug(): string | undefined {
    return (this.body as DuplicateError | null)?.existing_slug;
  }
}

/** A human-readable message for an error response.
 *
 * The message has to stay useful on its own, because that is what anything
 * doing `String(error)` will show. The pre-check's rejection reason arrives as
 * a plain `detail` string and is the most useful thing we can say; the gates
 * arrive as a `reason` code, which is at least specific. Deliberately not
 * polished user-facing copy — the UI reads `.reason` and writes its own. */
function explain(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;

  const reason = (body as { reason?: unknown } | null)?.reason;
  if (typeof reason === "string") return `${reason} (HTTP ${status})`;

  return `HTTP ${status}`;
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new ApiError(res.status, await res.json().catch(() => null));
  }
  return res.json() as Promise<T>;
}

export async function createReport(
  idea: string,
  targetUser?: string,
  force = false,
): Promise<CreatedReport> {
  const res = await fetch(`${API_URL}/reports`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Anon-Id": anonId() },
    body: JSON.stringify({ idea, target_user: targetUser || null, force }),
  });
  return parse<CreatedReport>(res);
}

export async function getReport(slug: string): Promise<Report> {
  return parse<Report>(await fetch(`${API_URL}/reports/${slug}`));
}

export async function listReports(): Promise<ReportSummary[]> {
  const res = await fetch(`${API_URL}/reports`, {
    headers: { "X-Anon-Id": anonId() },
  });
  return parse<ReportSummary[]>(res);
}
