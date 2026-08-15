"""Orchestrates the end-to-end pipeline for a single job posting URL.

Stops after drafting — it never submits a form or sends an email on its own.
"""

import re
from pathlib import Path

import yaml
from anthropic import Anthropic

from src import tracker
from src.cover_letter import draft_cover_letter, load_style_samples
from src.emailer import draft_email
from src.extractor import extract_job_spec
from src.render import render_cover_letter, render_resume
from src.resume_tailor import tailor_resume
from src.scraper import fetch_posting_text


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text or "").strip().lower()
    return re.sub(r"[\s_-]+", "_", text) or "unknown"


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def run(url: str, config_path: str = "config.yaml") -> dict:
    config = load_config(config_path)
    client = Anthropic()  # reads ANTHROPIC_API_KEY from env

    master_resume = yaml.safe_load(Path(config["resume_path"]).read_text())

    print(f"[1/6] Fetching posting: {url}")
    posting_text = fetch_posting_text(url)

    print("[2/6] Extracting application instructions...")
    job_spec = extract_job_spec(client, posting_text, config["extraction_model"])
    print(f"      {job_spec['company']} — {job_spec['role_title']} (apply via {job_spec['application_method']})")
    if job_spec.get("special_instructions"):
        print("      Special instructions found:")
        for instr in job_spec["special_instructions"]:
            print(f"        - {instr}")

    print("[3/6] Tailoring resume...")
    tailored_resume = tailor_resume(client, master_resume, job_spec, config["tailoring_model"])

    print("[4/6] Drafting cover letter in your voice...")
    style_samples = load_style_samples(config["style_samples_dir"])
    letter_text = draft_cover_letter(client, tailored_resume, job_spec, style_samples, config["cover_letter_model"])

    print("[5/6] Rendering documents...")
    out_dir = Path(config["output_dir"]) / f"{slugify(job_spec['company'])}_{slugify(job_spec['role_title'])}"
    resume_path = out_dir / "resume.docx"
    letter_path = out_dir / "cover_letter.docx"
    render_resume(tailored_resume, resume_path)
    render_cover_letter(letter_text, tailored_resume.get("contact", {}), letter_path)
    (out_dir / "job_spec.yaml").write_text(yaml.dump(job_spec, sort_keys=False))

    if job_spec["application_method"] == "email" and job_spec.get("contact_email"):
        eml_path = draft_email(job_spec, letter_text, resume_path, letter_path, out_dir / "application_draft.eml")
        print(f"      Email draft: {eml_path}")

    print("[6/6] Recording in tracker...")
    conn = tracker.connect(config["db_path"])
    app_id = tracker.record_application(conn, url, job_spec, str(out_dir))

    print(f"\nDone. Application #{app_id} drafted at {out_dir}/")
    if job_spec["application_method"] in ("company_portal", "third_party_ats"):
        print(f"Next step: apply manually at {job_spec.get('portal_url') or url} using the documents above.")
    elif job_spec["application_method"] == "email":
        print("Next step: review application_draft.eml, then send it yourself or via `python -m src.cli send <id>`.")
    else:
        print("Application method was unclear from the posting — check job_spec.yaml and the original listing.")

    return {"application_id": app_id, "output_dir": str(out_dir), "job_spec": job_spec}
