#!/usr/bin/env python3
"""
142 e-CAPS — Railway web server
POST /submit  { "callsign": "CABLE" }  → runs the Playwright form filler and returns the result
GET  /        → serves the HTML frontend
"""

import asyncio
import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, expect

app = Flask(__name__, static_folder=".")

# ── CONFIG ────────────────────────────────────────────────────────────────────

FORM_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbxUJt9ClFvBQyum0AsoIy0Ve0dJkWBK6BvHlbYHiWAkQxhYMYJfZs0WEzOGJtp2unLJhA"
    "/exec?page=page2"
)

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

assert len(ANSWERS) == 60

# ── PLAYWRIGHT LOGIC ──────────────────────────────────────────────────────────

async def submit_ecaps(callsign: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        page = await browser.new_page()

        try:
            await page.goto(FORM_URL, wait_until="networkidle", timeout=60_000)

            sandbox = page.frame_locator("#sandboxFrame")
            form    = sandbox.frame_locator("#userHtmlFrame")

            await form.locator("#txtCap_0").wait_for(state="visible", timeout=30_000)

            for i, answer in enumerate(ANSWERS):
                await form.locator(f"#txtCap_{i}").fill(answer)

            await form.locator("#btn_chkAnswer").click()

            try:
                await expect(form.locator("#btn_submit")).to_be_enabled(timeout=30_000)
            except PlaywrightTimeoutError:
                try:
                    msg = await form.locator("#L_chkAnswer").text_content(timeout=3_000)
                except Exception:
                    msg = "(no feedback label found)"
                return {"ok": False, "message": f"Validation timed out. Server said: {msg}"}

            await form.locator("#txtCallsign").fill(callsign.strip().upper())
            await form.locator("#btn_submit").click()
            await page.wait_for_timeout(5_000)

            try:
                result = await form.locator("#L_submit").text_content(timeout=5_000)
                return {"ok": True, "message": result.strip()}
            except Exception:
                return {"ok": True, "message": "Submitted — could not read result label."}

        except Exception as e:
            return {"ok": False, "message": str(e)}
        finally:
            await browser.close()

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(force=True, silent=True) or {}
    callsign = (data.get("callsign") or "").strip()
    if not callsign:
        return jsonify({"ok": False, "message": "Callsign is required."}), 400

    result = asyncio.run(submit_ecaps(callsign))
    status = 200 if result["ok"] else 500
    return jsonify(result), status

# ── ENTRY ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
