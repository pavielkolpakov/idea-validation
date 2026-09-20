/** Local-only UI test server. It never calls model providers or writes to the API database. */
import { createServer } from "node:http";
import type { Report, ReportSummary } from "../lib/api";

const timestamp = "2026-09-20T10:00:00Z";
const body: NonNullable<Report["report"]> = {
  verdict:
    "A focused opportunity in a crowded category. Small design studios need a simpler way to get client feedback, but a general-purpose project tool will be hard to differentiate. Start with visual approvals and a clear handoff to invoicing. Validate willingness to pay with five studios before expanding the workflow.",
  subscores: {
    market_size: 78,
    novelty: 54,
    competitive_headroom: 48,
    feasibility: 86,
    timing: 72,
  },
  competitors: [
    {
      name: "Design review platform",
      domain: "example.com",
      what_they_do:
        "Centralizes client comments and approval workflows for creative teams.",
      funding_stage: "Bootstrapped",
      sources: [0],
    },
    {
      name: "Studio project suite",
      domain: "example.org",
      what_they_do:
        "Combines project management, documents, and client billing for service businesses.",
      funding_stage: null,
      sources: [1],
    },
  ],
  risks: [
    {
      text: "Existing project management products could add approval workflows as a feature.",
      sources: [0],
    },
    {
      text: "Small studios may not pay for another tool unless it replaces something they already use.",
      sources: [1],
    },
  ],
  differentiation: [
    {
      text: "Make visual approvals exceptionally easy for clients who don’t want another account.",
      sources: [0],
    },
    {
      text: "Focus on the transition from approved deliverable to paid invoice.",
      sources: [],
    },
  ],
  citations: ["https://example.com/research", "https://example.org/market"],
  degraded_agents: [],
};
function report(slug: string, extra: Partial<Report> = {}): Report {
  return {
    id: 1,
    public_slug: slug,
    status: "succeeded",
    step: null,
    error: null,
    score: 68,
    report: body,
    created_at: timestamp,
    updated_at: timestamp,
    ...extra,
  };
}
const reports = new Map<string, Report>([
  ["ui-complete", report("ui-complete")],
  [
    "ui-partial",
    report("ui-partial", {
      report: { ...body, degraded_agents: ["graveyard"] },
    }),
  ],
  [
    "ui-failed",
    report("ui-failed", {
      status: "failed",
      error: "Research provider temporarily unavailable",
      score: null,
      report: null,
    }),
  ],
  [
    "ui-queued",
    report("ui-queued", { status: "queued", score: null, report: null }),
  ],
]);
const ideas = new Map([
  [
    "ui-complete",
    "A client feedback and approvals workspace for independent design studios.",
  ],
  [
    "ui-partial",
    "A neighborhood marketplace for surplus food from independent cafés.",
  ],
  [
    "ui-failed",
    "A skills-first hiring platform for small teams and freelance specialists.",
  ],
  [
    "ui-queued",
    "A research assistant that helps local businesses compare software tools.",
  ],
]);
const starts = new Map<string, number>();
createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "http://localhost:3000");
  res.setHeader(
    "Access-Control-Allow-Headers",
    "content-type, authorization, x-anon-id",
  );
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  const send = (status: number, value: unknown) => {
    res.writeHead(status, { "content-type": "application/json" });
    res.end(JSON.stringify(value));
  };
  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }
  const url = new URL(req.url ?? "/", "http://localhost:8001");
  if (url.pathname === "/health") {
    send(200, { status: "ok" });
    return;
  }
  if (url.pathname === "/corpus/stats") {
    send(200, {
      ideas: { total: 126, embedded: 124 },
      entities: { total: 482, embedded: 470 },
      research_chunks: { total: 504, embedded: 498 },
    });
    return;
  }
  if (url.pathname === "/auth/claim") {
    send(200, { claimed: 1 });
    return;
  }
  if (url.pathname === "/reports" && req.method === "GET") {
    const history: ReportSummary[] = [...reports.values()].map((r) => ({
      public_slug: r.public_slug,
      idea: ideas.get(r.public_slug) ?? "UI test idea",
      status: r.status,
      score: r.score,
      created_at: r.created_at,
    }));
    send(200, history.reverse());
    return;
  }
  if (url.pathname === "/reports" && req.method === "POST") {
    let data = "";
    for await (const chunk of req) data += chunk;
    const input = JSON.parse(data);
    if (!req.headers["x-anon-id"]) {
      send(401, { detail: "Missing identity" });
      return;
    }
    if (input.idea.startsWith("duplicate") && !input.force) {
      send(409, { reason: "duplicate", existing_slug: "ui-complete" });
      return;
    }
    for (const reason of ["anon_quota", "user_quota", "ip_rate"]) {
      if (input.idea.startsWith(reason)) {
        send(429, { reason });
        return;
      }
    }
    if (input.idea.startsWith("reject")) {
      send(422, {
        detail: "Please describe a concrete product or business idea.",
      });
      return;
    }
    if (
      input.idea.length < 20 ||
      input.idea.length > 1500 ||
      input.target_user?.length > 280
    ) {
      send(422, { detail: "Invalid input length" });
      return;
    }
    const slug = `ui-run-${starts.size + 1}`;
    starts.set(slug, Date.now());
    ideas.set(slug, input.idea);
    reports.set(
      slug,
      report(slug, { status: "queued", score: null, report: null }),
    );
    send(202, { id: starts.size + 1, public_slug: slug, status: "queued" });
    return;
  }
  const slug = decodeURIComponent(url.pathname.replace("/reports/", ""));
  if (starts.has(slug)) {
    const elapsed = Date.now() - starts.get(slug)!;
    const current =
      elapsed < 2500
        ? report(slug, { status: "queued", score: null, report: null })
        : elapsed < 7000
          ? report(slug, {
              status: "running",
              step: elapsed < 5000 ? "researching (2/4)" : "judging",
              score: null,
              report: null,
            })
          : report(slug);
    reports.set(slug, current);
  }
  if (reports.has(slug)) send(200, reports.get(slug));
  else send(404, { detail: "report not found" });
}).listen(8001, "127.0.0.1", () =>
  console.log(
    "UI fixtures on http://localhost:8001. No real research or database writes.",
  ),
);
