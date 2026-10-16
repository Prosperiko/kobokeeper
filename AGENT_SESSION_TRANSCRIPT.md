# Appendix: The Copilot Agent Sessions That Built KoboKeeper

*Raw session logs, cleaned and annotated. The GitHub Copilot coding agent executed
the steps below inside the repository; a human supervised every phase, verified
each commit locally, and caught the bugs noted. This is the honest build log —
including where the agent ran out of quota and died mid-hardening.*

---

## Context

KoboKeeper was specified as a 6-phase build plan (skeleton → extraction pipeline →
vendor memory + review workflow → exports → UI polish → deployment). The agent was
instructed to work **phase by phase**, commit at each checkpoint, and **stop for
human approval between phases**. Three sessions, three human checkpoints, 10 agent
commits. ~164 Copilot premium credits consumed — the final session ended when the
quota died, with the important work already landed.

---

## Session 1 — "Building offline AI receipt bookkeeper" (6m 05s, ~13 credits)

Goal: Phase 1 skeleton, per spec.

```
Setting up environment
Clone repository Prosperiko/kobokeeper
Start 'runtime-tools' / 'github-mcp-server' / 'playwright' MCP servers
Show working directory and files
View README.md
Progress update: chore: outline phase 1 implementation plan
Scaffold Phase 1 project files and baseline implementation
View app/models.py, app/main.py, app/db.py
Install deps and verify app routes plus category seeding
Edit app/config.py
Add focused phase 1 smoke tests for startup and routing
Run focused Phase 1 tests
Edit app/routes/pages.py                     <-- found its own template bug
Re-run phase 1 tests after template fix       <-- and fixed it unprompted
Manually verify dashboard page renders
Call to runtime-tools-secret_scanning
Progress update: feat: scaffold phase 1 offline FastAPI skeleton
Confirm clean working tree after commit
```

**Human checkpoint 1.** Local verification (`pytest`, `uvicorn`) passed — with one
catch: the agent had pinned `rapidocr-onnxruntime==1.3.24`, a version that **does
not exist on PyPI** (a hallucinated version pin). Human fixed locally
(`1.2.3`), reported it back, and the agent applied the same fix on its branch.

## Session 2 — "Implement phase 2 extraction core" (~27 credits)

Goal: OCR pipeline + Gemma extraction, the heart of the product.

```
Progress update: chore: plan phase 2 implementation
Apply patches → app/services/extractor.py, app/services/ocr.py, app/schemas.py, tests
Progress update: feat: implement phase 2 extraction core
Install deps and run Phase 2 extractor tests once
Progress update: test: verify phase 2 extractor tests   (4 passed)
```

Delivered: Gemma system prompt with strict JSON schema, `temperature=0`,
`format="json"`, <20-char OCR guard before burning a model call, one-bounded-attempt
JSON repair, `ExtractError` carrying raw text for graceful degradation. OCR via
rapidocr-onnxruntime (images) and PyMuPDF 2x-rasterization (PDFs). 4 unit tests,
mocked — CI runs green without Ollama.

**Human checkpoint 2 (code review before Phase 3 approval).** Review of
`extractor.py` found two real issues the tests couldn't see:

1. **Bug:** a pydantic `ValidationError` (valid JSON, garbage values, e.g.
   `"total": "N/A"`) would escape as a 500 instead of the graceful manual-fallback
   path. Fix: wrap validation into `ExtractError`.
2. **Hardening:** `suggested_category` needed normalization (small models return
   lowercase/near-miss categories) — title-case + fuzzy match + `"Other"` fallback.

Both were sent back as a precise review note; the agent patched with tests.

## Session 3 — "Reviewing and fixing issues in receipt data extraction" (9m 45s, ~104 credits) ⚡ died on quota

The agent didn't just apply the review fixes — it built **all of Phase 3**
(vendor memory, review-form workflow, every template, real vendored htmx,
tests) plus unrequested security hardening, then ran out of credits.

```
View 13 files (reviewing the whole codebase first)
Progress update: chore: plan phase2 fixes and phase3 workflow
Apply 2 patches → extractor.py, test_extractor.py          (review fixes)
Run extractor tests for phase2 fixes
Progress update: fix: harden extractor validation and category normalization
Vendor real htmx minified file
Apply 10 patches → vendor_memory.py, pages.py, api.py,
                    base/dashboard/upload/review.html, style.css
Add reusable HTMX line-item row template
Apply 6 patches → conftest.py, test_vendor_memory.py, test_api.py
Progress update: feat: implement phase3 workflow foundations
Run phase 3 targeted tests once
Edit tests/test_vendor_memory.py                          <-- its own fixture bug
Re-run phase 3 targeted tests after fixture fix            <-- self-corrected
Edit tests/test_vendor_memory.py                          <-- DB fixture issue
Run phase 3 targeted tests after DB fixture fixes
Inspect modified files before final commit
Call to runtime-tools-secret_scanning
Progress update: test: fix vendor memory DB fixture usage
Check changes with Copilot code review and CodeQL
View app/routes/api.py:160-220
Apply 3 patches → api.py, api.py, pages.py                 (security hardening)
Add safe delete confirmation template fragment
Edit tests/test_api.py
Run targeted tests after security-hardening changes
Apply 2 patches → api.py, pages.py                         (flash cookie encoding)
Re-run targeted tests after flash cookie encoding fix
Call to runtime-tools-secret_scanning
Progress update: fix: harden flash and delete confirm rendering
Check changes with Copilot code review and CodeQL
Edit app/routes/api.py                                     (cookie-injection fix)
Run targeted tests after cookie-injection fix
Call to runtime-tools-secret_scanning
Progress update: fix: remove user-derived flash cookie content
─── session ended: "Quota is insufficient to finish this session" ───
```

**Where it died:** mid security-hardening, immediately after committing
`fix: remove user-derived flash cookie content`. Nothing was lost — the entire
workflow was already committed. (Lesson logged: the agent's self-review/CodeQL
passes are what ate the quota; human review is cheaper and, in this case, the
review that mattered happened at the checkpoints.)

---

## Ledger: who built what

| Layer | Author | Notes |
|---|---|---|
| Phases 1–3 (skeleton, extraction, vendor memory, UI, tests) | Copilot agent (supervised) | 10 commits; every phase human-verified locally before approval |
| Extractor hardening (validation wrap, category normalization) | Human review → agent patch | caught before Phase 3 stacked on top |
| rapidocr pin fix | Human caught, both fixed | hallucinated version `1.3.24` → `1.2.3` |
| Phase 4 (CSV/PDF export, seed script, Dockerfile, render.yaml) | Human-written (supervisor) | agent quota was dead; hand-written to spec |
| Phase 5–6 polish + deploy iteration | Human (URL 404 fix, zstd fix, 1B-model resize for 2GB instance) | three real deploy failures, all one-line fixes |
| Product direction, idea, verification, privacy scrub | Human | fixtures with real receipts kept out of the public repo |

**Scoreboard:** 19 automated tests green · first real receipt (PalmPay transfer)
extracted correctly end-to-end · ~27s per image on CPU · ₦0 API spend.
