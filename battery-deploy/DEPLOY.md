# Agency research battery (Miriam's design) — deploy notes

`index.html` is the complete, tested full-battery survey. It is a sibling of
the CPA pilot page: same backend, same interaction machinery, coral theme
(#f15747) to distinguish it at a glance.

## To deploy (from a session with access to the civicpowerlab org)

1. Create a new repository `civicpowerlab/agency-battery` (public).
2. Copy this folder's `index.html` to the repo root and push to main.
3. Settings -> Pages -> Deploy from branch -> main, root.
4. URL will be https://civicpowerlab.github.io/agency-battery/

Verify sha256 of index.html before pushing:
run `sha256sum index.html` and compare with the value in the commit message
that added this file.

## Configuration (no code edits needed)

All of the battery's optionality is driven by URL parameters, and the active
configuration is stored inside every submission payload:

- `?share=1` — adds the optional "share results within your organization"
  consent screen (aggregate consent; nested individual-coaching consent;
  explicit do-not-share option).
- `?exp=community,voice,cpa,traits` — turns on expansion blocks
  (any subset, or `exp=all`):
  community = deep group consciousness; voice = internal/external political
  efficacy + sense of power; cpa = the full CPA pool (mirrors the live
  civicpowerlab.github.io/cpa-scale pool; re-sync at wording freeze) plus the
  four additional collective-capacity items; traits = leadership,
  introversion/extraversion, setbacks, 18 adjectives.
- `?results=profile` — replaces the standard thank-you with the banded
  agency profile (low/medium/high per dimension with Miriam's coaching
  language, participation index, and the agency-behavior gap callout).

Defaults with no parameters: core battery only, standard thank-you.

Example arms:
- Research-only arm:   https://.../agency-battery/
- Full coaching arm:   https://.../agency-battery/?share=1&exp=all&results=profile

## Backend

Saves to the same Supabase project and `cpa_responses` table as the CPA
pilot, with `kind: "battery"` and `version: "battery-v0.1-aug2026"`, so all
project data lives in one table and filters cleanly by kind.

Bulletproofing (same standard as CPA v0.7+): every interaction persists to
localStorage and restores on reload; saves retry 3x with 20s timeouts; on
final failure a backup JSON auto-downloads with instructions to email it to
emckenna@hks.harvard.edu; leave-page warning while unsubmitted.

## Content notes

- Consent/intro reproduced verbatim from lizmckenna/agency-instrument-demo
  per the design doc ("keep consent and intro page unchanged from demo").
- Core blocks, share-consent text, coaching language, and closing text
  reproduced verbatim from "Agency instrument - full research battery
  (August 2026)".
- The Dawson linked-fate item uses "people who share your racial or ethnic
  background" instead of piping the respondent's group label, because
  demographics are collected at the end. If piped wording is wanted,
  demographics must move before the Working Together block.
- Accessibility: #f15747 fails WCAG AA for small white text (3.4:1), so it
  is used for surfaces, borders, and progress; selected states and text
  links use derived shades #d13a28 / #b3301f, which pass AA.
- The org-facing aggregate dashboard (design doc Option 3) is an analysis
  product, not a respondent-survey feature; it should be built from the
  collected data separately.
