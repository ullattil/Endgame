"""Fetches the rendered text of a job posting page."""

from playwright.sync_api import sync_playwright


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
        browser.close()
    if not text.strip():
        raise RuntimeError(f"Got empty page text from {url} — site may require login or block bots.")
    return text
