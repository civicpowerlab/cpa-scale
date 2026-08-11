# CPA scale v0.7 (merged) — ready to deploy

`index.html` in this folder is the complete, tested v0.7 page for
**civicpowerlab/cpa-scale** (GitHub Pages, single file at repo root).

It merges BOTH streams of today's work:

- commit 6b9b932 ("answer reviewer questions in the instrument itself"):
  multi-paragraph method note (relevance-to-CPA-as-a-whole, clarity-for-a-
  community-member, I-CVI dichotomisation, sorting-benchmarks explanation),
  one-month-window rationale box, aligned 7-point coverage grid + per-construct
  prompt, sharper relevance/clarity hintlines
- the approved v0.7 feature set: gc1 racial group consciousness item
  (21-item pool, v0.7-pool21 payloads), per-reviewer item randomization,
  fully labeled Lynn anchors, submit gated on completeness, consent block
  (contact: Liz McKenna, Civic Power Lab, HKS — emckenna@hks.harvard.edu),
  structured reviewer fields, instrument-elements review section, floating
  "Definitions" panel on the expert tab, all requested wording edits

Verified: `node --check` on scripts; headless-browser run of the full
instrument flow (21 items / 7 screens / gated continue / 21-row review
summary), expert tab (21 review items, 6 coverage cards incl. gc
single-indicator variant, 5 element cards, definitions panel open/close),
no console errors. The word "naive" appears nowhere.

sha256(index.html) = f3d588546afc527ffc40541b526ef153c75abaaa5be17fa7194e247d4be118b2

## To deploy (from a session with push access to civicpowerlab/cpa-scale)

    # in a clone of civicpowerlab/cpa-scale, base = 6b9b932 on main
    cp <this-folder>/index.html index.html
    sha256sum index.html   # must equal the hash above
    git add index.html
    git commit -m "v0.7: merge expert-review upgrades (gc1 21-item pool, randomization, labeled anchors, gated submit, consent, reviewer fields, elements review, definitions panel) with reviewer-feedback revisions"
    git push origin main

If main has moved past 6b9b932, review the newer commits before overwriting.
