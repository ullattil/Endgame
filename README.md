# Job Application Assistant

Given a job posting URL, this pipeline:

1. Fetches and reads the posting (Playwright — handles JS-rendered listings)
2. Extracts structured instructions: how to apply, what to send, any special requirements
3. Tailors your resume to the posting (rewords/reorders existing bullets — never invents experience)
4. Drafts a cover letter matching your own writing voice (from samples you provide)
5. Renders both to `.docx`, plus an `.eml` draft if the posting wants an emailed application
6. Logs the application to a local SQLite DB

It deliberately **stops before submitting anything**. Portal applications get you filled documents ready to upload; email applications get you a reviewable draft you send yourself (or via `send`, which always asks for interactive y/N confirmation — never sent automatically or in a batch).

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Then fill in:
- `.env` — your `ANTHROPIC_API_KEY` (from https://console.anthropic.com/). SMTP fields are optional, only needed if you want to send email applications via `send`.
- `data/master_resume.yaml` — your real experience, structured. The tailoring step only rewords/reorders/trims these bullets; it won't fabricate new ones.
- `data/style_samples/*.txt` — 5-10 samples of your own writing (past cover letters, application emails) so generated letters sound like you.

## Usage

```bash
# Process one posting end-to-end
python -m src.cli apply "https://example.com/jobs/123"

# See everything tracked so far
python -m src.cli list

# Send a previously drafted email application (asks for confirmation)
python -m src.cli send 3
```

Output for each job lands in `output/<company>_<role>/`: `resume.docx`, `cover_letter.docx`, `job_spec.yaml` (what was extracted from the posting), and `application_draft.eml` if applicable.

## Switching models

[config.yaml](config.yaml) sets the model per pipeline step, not globally:

```yaml
extraction_model: claude-sonnet-5
tailoring_model: claude-sonnet-5
cover_letter_model: claude-fable-5
```

Extraction and tailoring are structured/constrained tasks (JSON tool-use, factual grounding against your resume) — Sonnet's precision matters most there. The cover letter is the one step where a model's voice and creative writing strength actually show up, hence Fable there instead. Change any of the three independently to test a different model on a given step — no code changes needed, just edit the values and rerun `apply`.

## Notes

- Some job boards' ToS prohibit automated form submission (LinkedIn Easy Apply among them) — this tool prepares documents but doesn't click submit anywhere.
- Job postings are treated as untrusted text: if a posting contains text aimed at an AI reader ("ignore previous instructions", etc. — a known adversarial-posting trick), the extractor reports it under `special_instructions` rather than acting on it.
- CAPTCHAs and logins on portal sites are on you — the script doesn't attempt to bypass either.
