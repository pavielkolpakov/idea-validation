@AGENTS.md

# web/ — Next.js frontend

Next.js 16, App Router, TypeScript, Tailwind. Dev server on :3000; talks to the API on :8000.

> The `@AGENTS.md` import above is from `create-next-app` and matters: **this Next version has breaking changes versus older conventions.** Read the relevant guide under `node_modules/next/dist/docs/` before writing framework code.

## Files

| Path | Role |
|---|---|
| `app/page.tsx` | The only real page. Submit an idea, poll, dump raw JSON |
| `lib/api.ts` | Hand-written fetch helpers + `ApiError`. All API access goes through here |
| `lib/api.gen.ts` | **Generated — do not edit.** `make types` rebuilds it from `api/openapi.json` |
| `.env.local` | `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`) |

## State of play

**The API now rejects unauthenticated requests** (`401`), so `lib/api.ts` sends an anonymous id. The page itself is still the Phase 1 page — the report view, history and SSE are Slice 3/4 of Phase 4.

**Phase 1 UI is deliberately unstyled and deliberately dumb.** Its only jobs are proving the 202-plus-poll contract works from a browser and surfacing CORS problems early. Real report rendering waits for Phase 2, when the judge schema stops changing daily — don't invest in visual design against a schema that's still moving.

## Conventions

- The API returns **202 + a `public_slug`**, then the client polls `GET /reports/{slug}` every 1.5s until `status` is `succeeded` or `failed` (`TERMINAL` in `lib/api.ts`). Phase 4 replaces polling with SSE.
- **`X-Anon-Id` is sent by `lib/api.ts`** — a uuid minted once per browser and kept in `localStorage`. The server resolves it to an ordinary `users` row and grants it **one** free run; after that the API returns `429 {"reason": "anon_quota"}` and the UI is expected to ask for a sign-in. Clerk and `Authorization: Bearer` land in Slice 3, along with the one-time `POST /auth/claim` that moves the anonymous report onto the new account.
- **Types are generated, helpers are not.** `lib/api.gen.ts` comes from the backend's OpenAPI spec via `make types` and is committed (Vercel's build can't reach the API). `lib/api.ts` re-exports the useful names and keeps the fetch wrappers hand-written — the interesting part is the credential headers, and a generated client would bury them in middleware. After changing `api/app/schemas.py` or a route, run `make types` and commit both outputs.
- **Gate failures carry a `reason`.** `createReport` throws `ApiError`, which keeps the parsed body: `reason` is `anon_quota` | `user_quota` | `ip_rate` | `duplicate`, and a duplicate also carries `existingSlug`. These are the branches the UI is built on — don't collapse them into a generic error string.
- Typecheck with `npx tsc --noEmit`.

## Known noise

`npm audit` reports high-severity issues in transitive deps of Next 16.2.12 (postcss, sharp). npm's only proposed fix is downgrading to `next@9.3.3`, which is nonsense — there is nothing actionable. Don't run `npm audit fix --force`.
