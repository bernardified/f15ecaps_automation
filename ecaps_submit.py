#!/usr/bin/env python3
"""
142 e-CAPS Auto-Submitter
Fills and submits the weekly 149/142 SQN CAPS form automatically.

Requirements:
    pip install playwright --break-system-packages
    playwright install chromium
"""

import asyncio
import sys
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, expect

# ── CONFIG ────────────────────────────────────────────────────────────────────

FORM_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbxUJt9ClFvBQyum0AsoIy0Ve0dJkWBK6BvHlbYHiWAkQxhYMYJfZs0WEzOGJtp2unLJhA"
    "/exec?page=page2"
)

CALLSIGN = "CABLE"

# 60 answers in order (txtCap_0 → txtCap_59).
# The form uppercases everything before checking, but these are already uppercase.
ANSWERS = [
    # ── FIRE DURING START (GROUND) — txtCap_0 to 9 ──────────────────────────
    "ENG FIRE WARNING LT", "PUSH",
    "THROTTLE(S)",         "OFF",
    "FIRE EXT",            "DISCHARGE",
    "ENG MASTER SWS",      "OFF",
    "JFS SW",              "OFF",

    # ── AMAD FIRE (GROUND) — txtCap_10 to 19 ────────────────────────────────
    "AMAD LT",             "PUSH",
    "FIRE EXT",            "DISCHARGE",
    "THROTTLES",           "OFF",
    "ENG MASTER SWS",      "OFF",
    "JFS SW",              "OFF",

    # ── ABORT — txtCap_20 to 25 ──────────────────────────────────────────────
    "THROTTLES",           "IDLE",
    "BRAKES",              "APPLY",
    "HOOK",                "AS REQ",

    # ── BLEED AIR CAUTION (L or R comes on) — txtCap_26 to 27 ───────────────
    "AIR SOURCE KNOB",     "OPP SOURCE",

    # ── BLEED AIR CAUTION (remains on, affected engine) — txtCap_28 to 31 ───
    "THROTTLE",            "IDLE",
    "FIRE WARNING SYS",    "TEST",

    # ── BLEED AIR CAUTION (both L and R) — txtCap_32 to 35 ──────────────────
    "AIR SOURCE KNOB",     "OFF",
    "FIRE WARNING SYS",    "TEST",

    # ── POSITIVE g OOC RECOVERY — txtCap_36 to 43 ───────────────────────────
    "CONTROLS",            "SMOOTHLY NEUTRALIZE AND RELEASE",
    "RUDDER",              "SMOOTHLY OPP ROLL/YAW",
    "SPEED BRAKE",         "RETRACT",
    "THROTTLES",           "OUT OF AB",

    # ── NEGATIVE g OOC / DEPARTURE RECOVERY — txtCap_44 to 51 ──────────────
    "CONTROLS",            "SMOOTHLY NEUTRALIZE LATERALLY AND APPLY HALF AFT STICK",
    "RUDDER",              "SMOOTHLY OPP YAW",
    "SPEED BRAKE",         "RETRACT",
    "THROTTLES",           "OUT OF AB AND MATCHED",

    # ── LOSS OF BRAKES — txtCap_52 to 59 ────────────────────────────────────
    "HOOK",                "DOWN",
    "ANTI SKID SW",        "OFF OR PULSER",
    "EMER BRAKE/STEER HANDLE", "PULL",
    "THROTTLES",           "OFF",
]

assert len(ANSWERS) == 60, f"Expected 60 answers, got {len(ANSWERS)}"

# ── MAIN ─────────────────────────────────────────────────────────────────────

async def submit_ecaps(headless: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()

        print("→ Opening form...")
        await page.goto(FORM_URL, wait_until="networkidle", timeout=60_000)

        # The form is inside two nested iframes:
        #   outer page → #sandboxFrame → #userHtmlFrame
        sandbox = page.frame_locator("#sandboxFrame")
        form    = sandbox.frame_locator("#userHtmlFrame")

        print("→ Waiting for form to render...")
        await form.locator("#txtCap_0").wait_for(state="visible", timeout=30_000)

        print("→ Filling in all 60 answers...")
        for i, answer in enumerate(ANSWERS):
            await form.locator(f"#txtCap_{i}").fill(answer)
        print("   Done.")

        print("→ Clicking 'Check Answers'...")
        await form.locator("#btn_chkAnswer").click()

        print("→ Waiting for server validation (may take ~5 s)...")
        try:
            # Submit button starts disabled; becomes enabled when results[1] == 0
            await expect(form.locator("#btn_submit")).to_be_enabled(timeout=30_000)
        except PlaywrightTimeoutError:
            # Try to read the check-answer result label for a clue
            try:
                msg = await form.locator("#L_chkAnswer").text_content(timeout=3_000)
            except Exception:
                msg = "(no feedback label found)"
            print(f"✗ Validation timed out. Server response: {msg}")
            await browser.close()
            sys.exit(1)

        print("→ Entering callsign...")
        await form.locator("#txtCallsign").fill(CALLSIGN)

        print("→ Submitting...")
        await form.locator("#btn_submit").click()

        # Give the server a moment to process and update the result label
        await page.wait_for_timeout(5_000)

        try:
            result = await form.locator("#L_submit").text_content(timeout=5_000)
            print(f"\n✓ Submission result: {result.strip()}")
        except Exception:
            print("✓ Submit clicked; could not read result label.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(submit_ecaps(headless=False))   # headless=False lets you watch it run
