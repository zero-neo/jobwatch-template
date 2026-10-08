from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys

from dotenv import load_dotenv

from .emailer import check_email, notify_from_env
from .boards import collect_adzuna, load_searches
from .dedupe import dedupe
from .config import ConfigError, load_companies, load_filters
from .filters import JobFilter
from .pipeline import collect
from .sheets import check_connection, sync_from_env
from .storage import Store


_STARTERS = (
    ("config.example.yaml", "config.yaml"),
    ("companies.example.yaml", "companies.yaml"),
    ("searches.example.yaml", "searches.yaml"),
    (".env.example", ".env"),
)


def init_files() -> None:
    """Create your own config files from the templates, never overwriting existing ones."""
    for example, target in _STARTERS:
        if os.path.exists(target):
            print(f"{target}: already exists, left alone")
        elif not os.path.exists(example):
            print(f"{example} not found. Run this from the project folder.", file=sys.stderr)
        else:
            shutil.copy(example, target)
            print(f"{target}: created from {example}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="jobwatch")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--companies", default="companies.yaml")
    parser.add_argument("--searches", default="searches.yaml")
    parser.add_argument("--db", default="jobs.sqlite")
    parser.add_argument("--dry-run", action="store_true",
                        help="print matches without touching the database")
    parser.add_argument("--no-sheet", action="store_true",
                        help="skip the Google Sheet sync")
    parser.add_argument("--show-skipped", action="store_true",
                        help="list the listings skipped as not in English")
    parser.add_argument("--no-email", action="store_true",
                        help="skip the email digest")
    parser.add_argument("--init", action="store_true",
                        help="create config.yaml, companies.yaml and .env from the templates")
    parser.add_argument("--check", action="store_true",
                        help="validate the config and Google Sheet access, then exit")
    load_dotenv()  # reads .env if present; real environment variables take priority
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.init:
        init_files()
        return 0

    try:
        job_filter = JobFilter(load_filters(args.config))
        companies = load_companies(args.companies)
        searches = load_searches(args.searches) if os.path.exists(args.searches) else None
    except (ConfigError, OSError) as exc:
        print(f"Config problem: {exc}", file=sys.stderr)
        return 2

    if not companies and searches is None:
        print("Nothing to search: add companies to companies.yaml or create searches.yaml.",
              file=sys.stderr)
        return 2

    if args.check:
        kinds = ", ".join(sorted({c.ats for c in companies}))
        print(f"Config OK: {len(companies)} companies ({kinds or 'none'}).")
        if searches:
            print(f"Searches: Adzuna {', '.join(searches.countries)}, {len(searches.queries)} queries.")
        print(check_connection())
        print(check_email())
        return 0

    matched, errors = collect(companies, job_filter)
    if searches is not None:
        found, search_errors = collect_adzuna(searches, job_filter)
        matched += found
        errors += search_errors
    found_total = len(matched)
    matched = dedupe(matched)  # direct company sources come first, so they win

    sheet_error = email_error = False
    if args.dry_run:
        new = matched
    else:
        store = Store(args.db)
        new = store.add_new(store.drop_known_listings(matched))
        if not args.no_sheet:
            try:
                added = sync_from_env(store)
                if added is None:
                    print("Google Sheet not configured; skipping sync.")
                else:
                    print(f"{added} row(s) added to the Google Sheet.")
            except Exception as exc:  # auth, permissions, quota, network
                print(f"Sheet sync failed (jobs stay queued for next run): {exc}",
                      file=sys.stderr)
                sheet_error = True
        if not args.no_email:
            try:
                sent = notify_from_env(store)
                if sent is None:
                    print("Email not configured; skipping digest.")
                else:
                    print(f"Email digest sent ({sent} job(s))." if sent else "No new jobs to email.")
            except Exception as exc:  # login, network, rejected recipient
                print(f"Email failed (jobs stay queued for next run): {exc}", file=sys.stderr)
                email_error = True
        store.close()

    if found_total > len(matched):
        print(f"{found_total - len(matched)} repeat posting(s) merged.")
    if job_filter.non_english_dropped:
        print(f"{job_filter.non_english_dropped} listing(s) skipped as not in English.")
        if args.show_skipped:
            for job in job_filter.non_english_skipped:
                print(f"  skipped: {job.title} | {job.company}")
    label = "matching" if args.dry_run else "new"
    print(f"\n{len(new)} {label} job(s); {len(errors)} source error(s)")
    for job in new:
        print(f"- {job.title} | {job.company} | {job.location}\n  {job.url}")
    return 1 if sheet_error or email_error or (errors and not matched) else 0


if __name__ == "__main__":
    raise SystemExit(main())
