"""CLI entrypoint.

Usage:
  python -m src.cli apply <job_posting_url>
  python -m src.cli list
  python -m src.cli send <application_id>   # only for email-based applications
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from src import tracker
from src.emailer import send_email
from src.pipeline import load_config, run


def cmd_apply(args):
    run(args.url, args.config)


def cmd_list(args):
    config = load_config(args.config)
    conn = tracker.connect(config["db_path"])
    rows = tracker.list_applications(conn)
    if not rows:
        print("No applications yet.")
        return
    print(f"{'ID':<4} {'Company':<20} {'Role':<30} {'Method':<16} {'Status':<10} Created")
    for row in rows:
        app_id, company, role, method, status, created = row
        print(f"{app_id:<4} {(company or ''):<20} {(role or ''):<30} {(method or ''):<16} {status:<10} {created}")


def cmd_send(args):
    config = load_config(args.config)
    conn = tracker.connect(config["db_path"])
    rows = tracker.list_applications(conn)
    match = next((r for r in rows if r[0] == args.application_id), None)
    if not match:
        print(f"No application with id {args.application_id}", file=sys.stderr)
        sys.exit(1)

    out_dir = None
    for row in conn.execute("SELECT output_dir FROM applications WHERE id = ?", (args.application_id,)):
        out_dir = row[0]
    eml_path = Path(out_dir) / "application_draft.eml"
    if not eml_path.exists():
        print(f"No email draft found at {eml_path} — this application may not be email-based.", file=sys.stderr)
        sys.exit(1)

    send_email(eml_path)
    tracker.update_status(conn, args.application_id, "sent")


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Job application assistant")
    parser.add_argument("--config", default="config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_apply = sub.add_parser("apply", help="Process a job posting URL end-to-end")
    p_apply.add_argument("url")
    p_apply.set_defaults(func=cmd_apply)

    p_list = sub.add_parser("list", help="List tracked applications")
    p_list.set_defaults(func=cmd_list)

    p_send = sub.add_parser("send", help="Send a previously drafted application email")
    p_send.add_argument("application_id", type=int)
    p_send.set_defaults(func=cmd_send)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
