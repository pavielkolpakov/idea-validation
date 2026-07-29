@AGENTS.md

# web/ — Next.js frontend

Next.js 16, App Router, TypeScript, Tailwind. Dev server on :3000; talks to the API on :8000.

> The `@AGENTS.md` import above is from `create-next-app` and matters: **this Next version has breaking changes versus older conventions.** Read the relevant guide under `node_modules/next/dist/docs/` before writing framework code.

## Files

| Path | Role |
|---|---|
| `app/page.tsx` | The only real page. Submit an idea, poll, dump raw JSON |
| `lib/api.ts` | Typed fetch helpers + the `Report` type. All API access goes through here |
| `.env.local` | `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`) |

## State of play

**Phase 1 UI is deliberately unstyled and deliberately dumb.** Its only jobs are proving the 202-plus-poll contract works from a browser and surfacing CORS problems early. Real report rendering waits for Phase 2, when the judge schema stops changing daily — don't invest in visual design against a schema that's still moving.

## Conventions

- The API returns **202 + a `public_slug`**, then the client polls `GET /reports/{slug}` every 1.5s until `status` is `succeeded` or `failed` (`TERMINAL` in `lib/api.ts`). Phase 4 replaces polling with SSE.
- `X-Debug-User` is sent by `lib/api.ts` because auth is deferred. It disappears in Phase 4.
- Keep types in `lib/api.ts` in sync with `api/app/schemas.py` by hand for now — OpenAPI codegen lands in Phase 4, once the report schema settles.
- Typecheck with `npx tsc --noEmit`.

## Known noise

`npm audit` reports high-severity issues in transitive deps of Next 16.2.12 (postcss, sharp). npm's only proposed fix is downgrading to `next@9.3.3`, which is nonsense — there is nothing actionable. Don't run `npm audit fix --force`.
