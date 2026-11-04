"""Fetches the rendered text of a job posting page."""

import html
import json
import re
import sys

from playwright.sync_api import sync_playwright

# Below this, the scrape almost certainly missed the job description.
THIN_SCRAPE_CHARS = 1500


def _html_to_text(raw: str) -> str:
    text = html.unescape(raw)  # descriptions are often HTML-escaped inside the JSON
    text = re.sub(r"<br\s*/?>|</p>|</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _jobposting_descriptions(ld_json_blobs: list) -> list:
    """Pulls description text from schema.org JobPosting structured data. Many
    JS-heavy job sites keep the full description only here, not in visible text."""
    found = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("@type") == "JobPosting" and node.get("description"):
                found.append(_html_to_text(str(node["description"])))
            walk(node.get("@graph", []))

    for blob in ld_json_blobs:
        try:
            walk(json.loads(blob))
        except ValueError:
            continue
    return found


def fetch_posting_text(url: str, timeout_ms: int = 30000) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")
        except Exception:
            # Some sites never go fully idle (polling/analytics). Fall back
            # to whatever loaded within the timeout instead of failing outright.
            pass
        text = page.inner_text("body")
        ld_blobs = page.eval_on_selector_all(
            'script[type="application/ld+json"]', "els => els.map(e => e.textContent)"
        )
        browser.close()

    descriptions = _jobposting_descriptions(ld_blobs)
    if descriptions:
        text += "\n\nJOB DESCRIPTION (from the page's structured data):\n" + "\n\n".join(descriptions)

    if not text.strip():
        raise RuntimeError(f"Got empty page text from {url} — site may require login or block bots.")
    if len(text) < THIN_SCRAPE_CHARS:
        print(
            f"WARNING: only {len(text)} characters scraped from {url}. The job "
            "description is probably missing, so the extraction and letter will be "
            "guesses. Check job_spec.yaml before trusting the output.",
            file=sys.stderr,
        )
    return text
