# CPA scale

Public instrument and expert-review tool for the Collective Political Agency
scale. Static site, no build step: `index.html` is the whole app, `methods.html`
is the methods write-up, and GitHub Pages serves `main` at
https://civicpowerlab.github.io/cpa-scale/.

## House style

- **American spelling.** behavior, not behaviour; summarize, analyze,
  dichotomized, randomized, double-barreled.
- **No em dashes in prose.** Use parentheses, a colon, or a semicolon. The
  `— select —` dropdown placeholders are a UI convention and stay as they are.
- Keep the review tab short. Justification, citations, and rationale belong in
  `methods.html`, linked from the tab. A reviewer should reach the first item
  quickly.

## Backend

Supabase project `cpa-scale` (ref `xdujvtvjpwbvoonxjjqa`). Submissions POST to
`cpa_responses` with columns `kind` (`instrument` or `expert_review`),
`version`, `respondent`, `payload`. Schema and policies are in
`supabase-setup.sql`.

The key in the page is a publishable key and is meant to be public: the table
has an insert policy for `anon` and no select policy, so the key cannot read a
response back. Publishable (`sb_publishable_`) keys are not JWTs and must not be
sent as a bearer token; `saveToBackend` sends `Authorization` only when the key
is a legacy `eyJ...` JWT.

## Before deploying

Verify in a real browser rather than by reading the diff. Chromium is at
`/opt/pw-browsers/chromium`; drive it with Playwright via
`NODE_PATH=/opt/node22/lib/node_modules`. Egress to `supabase.co` and
`github.io` is blocked from the agent container, so intercept the request with
`page.route` to check its shape, and leave the live end-to-end check to a human.

Bump `BUILD` and the header badge on every deploy: a stale cached page and a
real fault otherwise look identical, and the failure panel reports the build,
host, and key prefix actually in use.

Deploy is `git push origin <branch>:main`; Pages builds in about 40 seconds.
