"""Composes application emails as .eml drafts.

Sending is deliberately not automatic: draft_email() always just writes a
.eml file you can open, review, and send yourself from your normal mail
client. send_email() exists for cases where you've reviewed the draft and
want the script to send it, but it always asks for an interactive y/N
confirmation first and reads credentials only from environment variables —
it will never send silently as part of a batch/background run.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def draft_email(job_spec: dict, body: str, resume_path: Path, cover_letter_path: Path, out_path: Path) -> Path:
    msg = EmailMessage()
    msg["Subject"] = f"Application for {job_spec.get('role_title', 'the role')} — {job_spec.get('company', '')}"
    msg["To"] = job_spec.get("contact_email") or "(fill in — no contact email found in posting)"
    msg.set_content(body)

    for path in (resume_path, cover_letter_path):
        if path.exists():
            msg.add_attachment(
                path.read_bytes(),
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=path.name,
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(msg))
    return out_path


def send_email(eml_path: Path, to_override: str = None) -> None:
    """Sends a previously-drafted .eml. Requires interactive confirmation."""
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    from_email = os.environ.get("FROM_EMAIL")

    if not all([host, username, password, from_email]):
        raise RuntimeError(
            "SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and FROM_EMAIL must be set "
            "in your environment (see .env.example) to send email."
        )

    from email import message_from_bytes

    msg = message_from_bytes(eml_path.read_bytes())
    to_addr = to_override or msg["To"]

    print(f"About to send:\n  From: {from_email}\n  To: {to_addr}\n  Subject: {msg['Subject']}")
    confirm = input("Send this email now? [y/N] ").strip().lower()
    if confirm != "y":
        print("Not sent.")
        return

    msg.replace_header("From", from_email) if "From" in msg else msg.__setitem__("From", from_email)
    if to_override:
        msg.replace_header("To", to_override)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
    print("Sent.")
