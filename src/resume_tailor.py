"""Tailors the master resume to a specific job spec.

The model is constrained to reordering, trimming, and rewording the bullets
that already exist in the master resume — it is explicitly told not to
invent experience, employers, or skills that aren't already present.
"""

import copy
import json

from anthropic import Anthropic

TAILOR_TOOL = {
    "name": "record_tailored_resume",
    "description": "Record a tailored version of the resume for this job.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "title": {"type": "string"},
                        "start": {"type": "string"},
                        "end": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["company", "title", "start", "end", "bullets"],
                },
            },
            "skills": {"type": "array", "items": {"type": "string"}},
            "leadership": {
                "type": "array",
                "description": "Subset of the master resume's leadership entries worth showing for this job, unchanged or lightly reworded.",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "org": {"type": "string"},
                        "start": {"type": "string"},
                        "end": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["role", "org", "start", "end", "bullets"],
                },
            },
            "projects": {
                "type": "array",
                "description": "Subset of the master resume's projects worth showing for this job, unchanged or lightly reworded.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "start": {"type": "string"},
                        "end": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "start", "end", "bullets"],
                },
            },
        },
        "required": ["summary", "experience", "skills", "leadership", "projects"],
    },
}


def _cap_bullets(tailored_entries: list, master_entries: list, match_keys: tuple) -> list:
    """Caps each entry's bullet count at the master entry's bullet count, matched by
    identity keys (e.g. company+title). Drops entries that don't exist in the master
    at all. This is a hard backstop against the model inventing new bullets or
    fabricating whole new entries — prompt instructions alone aren't reliable enough."""
    master_by_key = {tuple(e.get(k, "") for k in match_keys): e for e in master_entries}
    capped = []
    for entry in tailored_entries:
        key = tuple(entry.get(k, "") for k in match_keys)
        master_entry = master_by_key.get(key)
        if master_entry is None:
            continue  # not in master resume — drop rather than trust a fabricated entry
        max_bullets = len(master_entry.get("bullets", []))
        entry = dict(entry)
        entry["bullets"] = entry.get("bullets", [])[:max_bullets]
        capped.append(entry)
    return capped


def _filter_skills(tailored_skills: list, master_skills: list) -> list:
    master_set = {s.strip().lower(): s for s in master_skills}
    seen = set()
    filtered = []
    for skill in tailored_skills:
        key = skill.strip().lower()
        if key in master_set and key not in seen:
            filtered.append(master_set[key])
            seen.add(key)
    return filtered


def tailor_resume(client: Anthropic, master_resume: dict, job_spec: dict, model: str) -> dict:
    prompt = (
        "Tailor this resume to the job below. Rules:\n"
        "- Do not invent employers, titles, dates, skills, or achievements that "
        "aren't already in the master resume.\n"
        "- Every bullet you output must be a REWORDING of one specific existing "
        "bullet from that same entry in the master resume — never add a new "
        "bullet that has no corresponding source bullet, even if it seems "
        "true or reasonable. You may reorder and trim bullets, but the "
        "output for an entry can never have MORE bullets than the master "
        "resume has for that entry.\n"
        "- When rewording, preserve concrete numbers/metrics from the "
        "original bullet (percentages, dollar amounts, counts) — don't drop "
        "them in favor of generic phrasing.\n"
        "- Skills must be chosen only from the exact strings in the master "
        "resume's skills list — do not combine, rename, or synthesize new "
        "skill labels (e.g. don't turn 'Python' + job history into a new "
        "label like 'Backend Development'). You may only reorder/select a "
        "subset of the existing list.\n"
        "- Keep every employer/title/date entry from the master resume's "
        "experience list unless instructed otherwise; just adjust which "
        "bullets are shown and how they're worded.\n"
        "- For leadership and projects: these are optional sections. Include "
        "only entries that already exist in the master resume and are "
        "actually relevant to this job; omit entries that would just be "
        "noise. Return empty arrays if none are relevant — never invent new "
        "ones.\n"
        "- Prioritize skills/bullets that match the job's key_requirements.\n\n"
        f"MASTER RESUME (JSON):\n{json.dumps(master_resume, indent=2)}\n\n"
        f"JOB SPEC (JSON):\n{json.dumps(job_spec, indent=2)}"
    )
    resp = client.messages.create(
        model=model,
        max_tokens=3000,
        tools=[TAILOR_TOOL],
        tool_choice={"type": "tool", "name": "record_tailored_resume"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            tailored = copy.deepcopy(master_resume)
            tailored["summary"] = block.input["summary"]
            tailored["experience"] = _cap_bullets(
                block.input["experience"], master_resume.get("experience", []), ("company", "title")
            )
            tailored["skills"] = _filter_skills(block.input["skills"], master_resume.get("skills", []))
            tailored["leadership"] = _cap_bullets(
                block.input["leadership"], master_resume.get("leadership", []), ("role", "org")
            )
            tailored["projects"] = _cap_bullets(
                block.input["projects"], master_resume.get("projects", []), ("name",)
            )
            return tailored
    raise RuntimeError("Model did not return structured output for resume tailoring.")
