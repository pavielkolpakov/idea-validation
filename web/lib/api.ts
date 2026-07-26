const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ReportStatus = "queued" | "running" | "succeeded" | "failed";

export interface Report {
  id: number;
  public_slug: string;
  status: ReportStatus;
  step: string | null;
  error: string | null;
  score: number | null;
  report: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CreatedReport {
  id: number;
  public_slug: string;
  status: ReportStatus;
}

export const TERMINAL: ReportStatus[] = ["succeeded", "failed"];

export async function createReport(
  idea: string,
  targetUser?: string,
): Promise<CreatedReport> {
  const res = await fetch(`${API_URL}/reports`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Debug-User": "dev" },
    body: JSON.stringify({ idea, target_user: targetUser || null }),
  });
  if (!res.ok) {
    throw new Error(`create failed (${res.status}): ${await res.text()}`);
  }
  return res.json();
}

export async function getReport(slug: string): Promise<Report> {
  const res = await fetch(`${API_URL}/reports/${slug}`);
  if (!res.ok) {
    throw new Error(`fetch failed (${res.status})`);
  }
  return res.json();
}
