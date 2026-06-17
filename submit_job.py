#!/usr/bin/env python3
"""
One-shot CAPS / Ops Limit submitter for scheduled (Railway cron) runs.

Usage:
    python submit_job.py <caps|opslimit> [CALLSIGN]

CALLSIGN comes from the 2nd argument, else the CALLSIGN env var, else "CABLE".
Reuses submit_form() from app.py (its own headless Chromium), so it does NOT
need the web service to be running. Prints the result to stdout (captured in
Railway logs) and exits 0 on success, 1 on failure, 2 on bad usage.
"""

import asyncio
import os
import sys

from app import submit_form, FORMS


def main() -> int:
    form = (sys.argv[1] if len(sys.argv) > 1 else "caps").strip().lower()
    callsign = (
        sys.argv[2] if len(sys.argv) > 2 else os.environ.get("CALLSIGN", "CABLE")
    ).strip()

    if form not in FORMS:
        print(f"Unknown form '{form}'. Use one of: {', '.join(FORMS)}")
        return 2

    result = asyncio.run(submit_form(form, callsign))
    status = "OK" if result.get("ok") else "FAIL"
    print(f"[{status}] {form} / {callsign}: {result.get('message')}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
