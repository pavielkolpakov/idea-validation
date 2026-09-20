@AGENTS.md

# web/ — Next.js frontend

Next.js 16 App Router, React 19, TypeScript, Tailwind v4, Clerk, and Phosphor icons. Read the relevant Next guide under `node_modules/next/dist/docs/` before changing framework code.

## Structure

- `app/page.tsx`: picks one of two pages off `signedIn` — the marketing landing, or the workspace (idea composer, optional audience, draft preservation, submission gates, recent history).
- `components/landing.tsx`: the signed-out sections below the hero — feature cards, steps, FAQ, closing CTA.
- `app/reports/page.tsx`: history, local search and status filters (latest 100 reports).
- `app/reports/[slug]/page.tsx` and `components/report-view.tsx`: public report, polling, scores, citations, sharing and JSON download.
- `app/research/page.tsx`: corpus totals, embedding counts and service health.
- `components/providers.tsx`: Clerk identity, anonymous fallback, history and report claiming.
- `components/shell.tsx`: the marketing frame when signed out, the workspace sidebar once signed in.
- `components/seed-hero.tsx`: centred hero — copy, two CTAs, then the full-width `SeedMotion` diagram. **Signed-out only.**
- `app/globals.css`: design tokens, light theme and responsive layouts (see **Design system** below).
- `lib/api.ts`: all HTTP requests, credential headers, error translation and safe source URLs.
- `lib/api.gen.ts`: generated from `api/openapi.json` by `make types`; do not edit by hand.

## Design system

Palette and shape are derived from Monad (`monad.com`); **typography is not** —
headings and body stay on Geist Sans at the original weights and tracking.

Tokens live in `:root` in `app/globals.css` — use them instead of new literals:

| Token | Value | Use |
|---|---|---|
| `--background` | `#f6f3f1` | Parchment page canvas |
| `--paper` | `#fffdfc` | Cards and panels |
| `--foreground` / `--ink` | `#242424` | Off-Black text |
| `--muted` | `#4e4d4d` | Graphite secondary text |
| `--border` | `#cecac8` | Ash hairline on cards and controls |
| `--line` | `#dfdad7` | Internal rules and row dividers |
| `--wash` | `#efebe8` | Tinted surfaces |
| `--accent` | `#41734a` | The single accent, in place of Monad's Lake Blue |
| `--radius` / `--radius-sm` / `--pill` | `40px` / `20px` / `100px` | Cards / inputs / buttons and tags |

Conventions:

- **Cards use a 1px `--border` hairline, never a shadow.**
- Only one primary (green) button per screen; everything else is a transparent
  pill with an Ash border.
- The hero follows Monad's layout: centred eyebrow, headline and subcopy, two
  centred CTAs, then the diagram full width beneath. `.seed-hero-wash` is the
  soft blurred gradient behind it — decorative pastels live there and in the SVG
  diagram, never in functional UI.

`components/seed-motion.tsx` holds three motion directions, previewable at
`/design/seed-motion`. **The hero is locked to `engine` ("Growth engine")**; the
other two are kept for that review page only.

## Access

**There is no anonymous workspace in the UI.** Signed-out visitors get the
marketing frame — no sidebar, no composer, no history — and every call to action
opens Clerk's sign-in modal. The composer, the examples and the recent-reports
list render only once `useIdentity().signedIn` is true. The backend's anonymous
identity and its one-report quota still exist and public report links still
resolve for anyone; nothing in the UI creates an anonymous run any more.

**The two states are different pages, not one page with extras.** Signed out is
the pitch: hero, then `<Landing />`. Signed in, the pitch is over — the hero and
the marketing sections are gone entirely and the page opens on the composer
under a short `.intro` heading. Don't reintroduce the hero for signed-in users.

The landing's cards carry mock report fragments (`.mock-chips`, `.mock-rows`,
`.mock-score`, `.mock-sources`) — **illustrative constants in `landing.tsx`, not
live data.** Reveal-on-scroll uses `animation-timeline: view()` behind an
`@supports` guard, so browsers without it simply render the cards; the global
`prefers-reduced-motion` rule turns it off.

## API behavior

The API returns `202 + public_slug`. Poll `GET /reports/{slug}` every 1.5 seconds until `succeeded` or `failed`; there is no SSE endpoint in this version. Public report reads need no authentication and omit the original idea text. The owner's history provides a 200-character idea preview.

Guest identity is a UUID stored as `ideacheck-anon-id` in localStorage and sent in `X-Anon-Id`. Clerk sessions provide `Authorization: Bearer` tokens. The client gets a fresh token for each authenticated operation. After sign-in, `POST /auth/claim` transfers guest reports; failures expose a retry. Use the publishable key for the same Clerk instance as the backend. No frontend secret key is required.

Submission gates are distinct: `anon_quota`, `user_quota`, `ip_rate`, and `duplicate`. A duplicate includes `existing_slug` and can be retried with `force: true`. Precheck rejection text is shown directly. Treat report citations as zero-based indices and display them as one-based source numbers; only HTTP(S) source links are clickable.

## Verification

`npm run lint`, `npx tsc --noEmit`, `npm test`, and `npm run build`. Node 22.7+ is needed for the built-in test runner's TypeScript transformation. `npm run test:fixtures` serves local UI test data on port 8001; see README for browser verification and restoring the real API. Fixtures do not call model providers or write to the database.
