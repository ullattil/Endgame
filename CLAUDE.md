# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A job-application pipeline: given a job posting URL, it fetches the posting, extracts structured
application instructions, tailors the resume to the posting, drafts a cover letter in the user's
voice, renders both to `.docx`, and stops for human review before anything is sent or submitted.

## Commands

```bash
# Setup (one-time)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium   # scraper.py will fail without this
cp .env.example .env                     # then fill in ANTHROPIC_API_KEY for real use

# Run
.venv/bin/python -m src.cli apply "<job posting url>"
.venv/bin/python -m src.cli list
.venv/bin/python -m src.cli send <application_id>   # only for email-method applications

# Compile check (there is no test suite — this is the actual verification step used so far)
python3 -m py_compile src/*.py
```

There are no automated tests. Changes to `resume_tailor.py`, `cover_letter.py`, or `render.py` have
so far been verified with one-off smoke scripts run through `.venv/bin/python -c "..."` (render a
sample resume, check output word/line counts, diff tailored bullets against `master_resume.yaml`)
rather than a formal test file. Follow that pattern rather than assuming a `pytest` setup exists.

## Architecture

Pipeline stages, orchestrated by `src/pipeline.py` and invoked via `src/cli.py`:

```
scraper.py → extractor.py → resume_tailor.py → cover_letter.py → render.py → tracker.py / emailer.py
```

- **`config.yaml`** sets the model **per pipeline step**, not globally: `extraction_model`,
  `tailoring_model`, `cover_letter_model`. Extraction/tailoring are structured, tool-use-constrained
  tasks where precision matters most; the cover letter is the one step where a model's voice
  actually shows up, which is why it's configured independently. When adding a new LLM-calling step,
  give it its own config key rather than reusing an existing one or reintroducing a global `model`.

- **`data/master_resume.yaml` is the single source of truth** for the candidate's real experience.
  Nothing downstream is allowed to introduce facts, bullets, skills, or entries that aren't already
  there. This is enforced at the code level in `resume_tailor.py` (`_cap_bullets` truncates each
  tailored entry to the master entry's bullet count; `_filter_skills` intersects tailored skills
  against the exact master skills list) — **not just by prompt instruction**. This guardrail exists
  because prompt-only instructions ("don't invent achievements") were tried first and the model
  still fabricated bullets and synthesized skill labels in testing. Any change to the tailoring or
  cover-letter logic must preserve a code-level check, not rely on asking the model nicely.

- **Job postings are untrusted external content.** `extractor.py`'s prompt explicitly tells the
  model to record — but not obey — any text in a posting addressed to an AI reader (prompt
  injection via job listings is a known adversarial pattern). Preserve this framing if the
  extraction prompt is modified.

- **The pipeline never auto-submits or auto-sends.** `pipeline.run()` always stops after drafting.
  `emailer.py`'s `send_email()` requires an interactive y/N confirmation read from stdin and reads
  SMTP credentials only from environment variables — it is never called as part of a batch/background
  run. Don't add a path that sends or submits without a human confirmation step in between.

- **Output layout**: each processed posting lands in `output/<company>_<role>/` containing
  `resume.docx`, `cover_letter.docx`, `job_spec.yaml` (the raw extraction result, kept for
  debugging/audit), and `application_draft.eml` when the application method is email.

- **`render.py` targets a one-page resume** (compact margins, right-aligned dates via tab stops,
  tight paragraph spacing). There is no local tool that reliably renders paginated DOCX → the
  Pages app (`com.apple.Pages`, "Pages Creator Studio" as of macOS Tahoe) can be scripted via
  `osascript` to export a real paginated PDF for verification — this is more reliable than
  estimating line/word counts by hand. LibreOffice, Word, and `textutil -convert pdf` are not
  available in this environment for docx→pdf conversion.

## Working on this project

Stay scoped to what's actually asked rather than expanding a request into an unrequested redesign —
this project has accumulated deliberate, incremental decisions (per-step models, code-level
anti-fabrication guardrails, human-confirmation gates) that were each made in response to a specific
problem, not speculative future-proofing. When a change touches `resume_tailor.py` or
`cover_letter.py`, verify the fix by actually running the tailoring/generation against a real or
saved `job_spec.yaml` and diffing the output against `master_resume.yaml`, rather than trusting a
prompt change alone.
