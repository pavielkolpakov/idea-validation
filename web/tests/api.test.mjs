import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import {
  ApiError,
  claimReports,
  createReport,
  errorMessage,
  getReport,
  getCorpusStats,
  getHealth,
  listReports,
  safeUrl,
} from "../lib/api.ts";

const originalFetch = globalThis.fetch;
let calls;
let response;
const storage = new Map();
beforeEach(() => {
  calls = [];
  response = new Response(
    JSON.stringify({ status: "queued", public_slug: "example" }),
    { status: 202 },
  );
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
    },
  });
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return response;
  };
});
afterEach(() => {
  globalThis.fetch = originalFetch;
  storage.clear();
  delete globalThis.localStorage;
});

test("anonymous submissions preserve identity and send idea, audience, and force", async () => {
  await createReport(
    "A useful idea with enough detail",
    "Independent studios",
    true,
  );
  const id = calls[0].init.headers.get("X-Anon-Id");
  assert.match(id, /^[a-f0-9-]{36}$/);
  assert.equal(calls[0].init.headers.has("Authorization"), false);
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    idea: "A useful idea with enough detail",
    target_user: "Independent studios",
    force: true,
  });
  response = new Response("[]");
  await listReports();
  assert.equal(calls[1].init.headers.get("X-Anon-Id"), id);
  assert.match(calls[1].url, /\/reports\?limit=100$/);
});

test("signed-in requests send a fresh bearer token and the claim retains the anonymous identity", async () => {
  await createReport("A useful idea with enough detail", "", false, {
    token: "first-token",
  });
  response = new Response('{"claimed":1}');
  const claimed = await claimReports({ token: "refreshed-token" });
  assert.equal(
    calls[0].init.headers.get("Authorization"),
    "Bearer first-token",
  );
  assert.equal(
    calls[1].init.headers.get("Authorization"),
    "Bearer refreshed-token",
  );
  assert.equal(
    calls[1].init.headers.get("X-Anon-Id"),
    calls[0].init.headers.get("X-Anon-Id"),
  );
  assert.match(calls[1].url, /\/auth\/claim$/);
  assert.equal(calls[1].init.method, "POST");
  assert.equal(claimed.claimed, 1);
  assert.equal(JSON.parse(calls[0].init.body).target_user, null);
});

test("public report requests are anonymous, escaped, cancellable, and uncached", async () => {
  const controller = new AbortController();
  await getReport("a/b?c", controller.signal);
  assert.match(calls[0].url, /\/reports\/a%2Fb%3Fc$/);
  assert.equal([...calls[0].init.headers].length, 0);
  assert.equal(calls[0].init.signal, controller.signal);
  assert.equal(calls[0].init.cache, "no-store");
});

for (const reason of ["anon_quota", "user_quota", "ip_rate", "duplicate"]) {
  test(`preserves the ${reason} submission gate`, async () => {
    response = new Response(
      JSON.stringify({ reason, existing_slug: "previous" }),
      { status: reason === "duplicate" ? 409 : 429 },
    );
    await assert.rejects(
      createReport("A useful idea with enough detail"),
      (error) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.reason, reason);
        if (reason === "duplicate")
          assert.equal(error.existingSlug, "previous");
        return true;
      },
    );
  });
}

test("precheck and field validation messages remain useful", async () => {
  response = new Response('{"detail":"Please describe a business idea."}', {
    status: 422,
  });
  await assert.rejects(
    createReport("Not a business submission"),
    /Please describe a business idea/,
  );
  response = new Response('{"detail":[{"msg":"Idea is too long"}]}', {
    status: 422,
  });
  await assert.rejects(
    createReport("A useful idea with enough detail"),
    /Idea is too long/,
  );
});

test("non-JSON and network errors have recoverable messages", async () => {
  response = new Response("Service unavailable", { status: 503 });
  await assert.rejects(getReport("missing"), /Please try again/);
  assert.match(
    errorMessage(new TypeError("Failed to fetch")),
    /couldn’t reach/,
  );
  assert.match(errorMessage(new ApiError(404, null)), /couldn’t find/);
  assert.match(errorMessage(new ApiError(401, null)), /sign in again/);
});

test("library statistics and health use public endpoints", async () => {
  await getCorpusStats();
  response = new Response('{"status":"ok"}');
  await getHealth();
  assert.match(calls[0].url, /\/corpus\/stats$/);
  assert.match(calls[1].url, /\/health$/);
  assert.equal([...calls[0].init.headers].length, 0);
});

test("citation links never execute script or open local/data URLs", () => {
  for (const url of [
    "javascript:alert(1)",
    "data:text/html,hi",
    "file:///etc/passwd",
    "//example.com",
    "invalid",
  ])
    assert.equal(safeUrl(url), null);
  assert.equal(
    safeUrl("https://example.com/source"),
    "https://example.com/source",
  );
});
