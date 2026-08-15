"""Drafts a cover letter in the user's own voice, using writing samples as few-shot examples."""

from pathlib import Path

from anthropic import Anthropic


def load_style_samples(style_samples_dir: str) -> list:
    samples = []
    for path in sorted(Path(style_samples_dir).glob("*.txt")):
        text = path.read_text().strip()
        if text:
            samples.append(text)
    return samples


def draft_cover_letter(
    client: Anthropic,
    tailored_resume: dict,
    job_spec: dict,
    style_samples: list,
    model: str,
) -> str:
    if not style_samples:
        raise RuntimeError(
            "No style samples found in data/style_samples/. Add a few .txt files "
            "of your own past writing so the letter can match your voice."
        )

    samples_block = "\n\n---\n\n".join(style_samples)

    prompt = (
        "Write a cover letter for the job below, in the voice of the writing "
        "samples provided. Match their tone, sentence length, vocabulary, and "
        "level of formality closely — don't default to generic corporate "
        "cover-letter phrasing ('I am writing to express my interest...', "
        "'I am confident that my skills...').\n\n"
        "Strict grounding rule: every specific claim about something the "
        "candidate did — a project, a responsibility, an outcome, a metric, "
        "an act like mentoring/training/leading — must correspond to a "
        "bullet that is already present in the TAILORED RESUME JSON below. "
        "Do not invent additional activities or responsibilities beyond what "
        "those bullets state, even minor-sounding ones (e.g. don't add "
        "'I mentored junior staff' unless a bullet already says that). You "
        "MAY explain, connect, and draw out the relevance of existing "
        "bullets in your own words — that's the point of a cover letter — "
        "but every underlying fact must trace back to one of them.\n"
        "If the job wants something the resume doesn't show (e.g. a specific "
        "tool or certification), it's fine and often stronger to say so "
        "honestly and pivot to a related strength, rather than imply "
        "experience that isn't there.\n\n"
        f"JOB SPEC (JSON):\n{job_spec}\n\n"
        f"TAILORED RESUME (JSON):\n{tailored_resume}\n\n"
        f"WRITING SAMPLES (for voice/style only, not content):\n{samples_block}\n\n"
        "Keep it to roughly 300-400 words (one page) — tight and specific "
        "beats exhaustive.\n\n"
        "Output only the cover letter body text, no subject line or salutation "
        "placeholders beyond a normal greeting/sign-off."
    )

    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()
