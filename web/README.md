# IdeaCheck frontend

Next.js App Router frontend for the current IdeaCheck API. The design follows the light surfaces, thin headings, forest-green and sage palette, and rounded controls of the [Rootly reference](https://styles.refero.design/style/a037c352-4315-4650-a16c-08392ffca597).

## Run locally

```sh
cp .env.example .env.local
npm install
npm run dev
```

Run the API separately with `make api` from the repository root (Postgres must be running and migrated). The web app is at http://localhost:3000.

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`. Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` to the public key of the same Clerk instance configured by the API's `CLERK_JWKS_URL`. The frontend uses Clerk's client-side session and obtains a fresh bearer token for authenticated requests. No Clerk secret key is needed by this frontend. Without a publishable key, anonymous workflows and public reports still work; account access is unavailable.

## API coverage

| Screen / behavior | API |
| --- | --- |
| Idea and optional target audience, with duplicate rerun | `POST /reports` |
| Report history, search, status filter, refresh | `GET /reports?limit=100` |
| Public shareable reports, polling, verdict, weighted subscores, competitors, risks, differentiation, citations, partial/failure states, JSON export | `GET /reports/{public_slug}` |
| Transfer guest reports after sign-in, with retry on failure | `POST /auth/claim` |
| Research library totals and indexed counts | `GET /corpus/stats` |
| Service availability in research library | `GET /health` |

All HTTP requests are in `lib/api.ts`. Report types come from `lib/api.gen.ts`; regenerate with `make types` when the API contract changes. No backend behavior was changed.

The API has no SSE endpoint, so report pages poll every 1.5 seconds until success or failure, cancelling requests on navigation. Request failures expose a retry action. History is limited to the latest 100 records by the backend; filtering searches those records. The report endpoint omits the original idea, so public reports use a neutral title; the owner's idea preview is shown when available from history. The library API exposes aggregate counts only.

## Checks

```sh
npm run lint
npx tsc --noEmit
npm test
npm run build
```

The API regression tests use Node's built-in runner and TypeScript transformation (Node 22.7+). They verify anonymous identity, token forwarding, claims, payloads, cancellation, submission gates, errors, and safe citation URLs.

## Reproducible UI checks without paid research

In one terminal:

```sh
npm run test:fixtures
```

Stop any existing frontend dev server, then in another terminal:

```sh
NEXT_PUBLIC_API_URL=http://localhost:8001 npm run dev
```

This uses a local-only fixture service, with no database writes or model-provider calls. Never use it as a deployed API. Open http://localhost:3000 and verify:

- Empty/short input disables submission. Examples populate both fields. Drafts survive navigation and reload.
- Valid submission transitions through queued, research, assessment, and a complete report. Navigation away and back resumes polling.
- History filters, public report links, citation anchors, sharing, and JSON download work.
- Seeded reports include completed, failed, queued, and partial research states.
- Start an idea with `duplicate`, `anon_quota`, `user_quota`, `ip_rate`, or `reject` (at least 20 characters total) to exercise each submission gate. A forced duplicate rerun proceeds normally.
- Research statistics load, and unavailable API requests show retry controls.
- Mobile navigation and report content fit a 390px viewport.

Restart `npm run dev` without the API override to return to the real backend. Clerk's modal can be checked with the configured public key. Completing sign-in and verifying report transfer against Clerk requires an authenticated user session.

## Seed identity and hero motion

The leaf mark is retained. The workspace now uses forest-green accents, sage surfaces, and the idea-as-seed story. The hero is a native SVG animation inspired by Monad’s flowing connector diagram; no video service, added runtime dependency, or paid generation is required.

Compare three animated directions at `/design/seed-motion`: **Growth engine**, **Roots before growth**, and **Seed to skyline**. Each direction has a “Preview in workspace” link. The `?motion=engine|roots|skyline` parameter previews that direction on the home page; Growth engine remains the default until a direction is chosen.

Animations have pause/replay controls, pause off-screen, and respect reduced-motion preferences. The diagrams illustrate validation and possible outcomes. They do not call the API, represent report progress, or promise a successful business. The composer remains connected to the real API.
