#!/usr/bin/env python3
"""
142 e-CAPS — Railway web server
POST /submit  { "callsign": "CABLE", "form": "caps" | "opslimit" }
              → runs the Playwright form filler for the chosen form and returns the result
GET  /        → serves the HTML frontend

Two forms share one Playwright flow (see FORMS below):
  • caps     — weekly CAPS emergency-procedure form  (60 answers, page2)
  • opslimit — monthly Ops Limit aircraft-limits form (61 answers, opslimit)
"""

import asyncio
import os
from flask import Flask, request, jsonify, send_from_directory
from playwright.async_api import async_playwright

app = Flask(__name__, static_folder=".")

# ── CONFIG ────────────────────────────────────────────────────────────────────

_BASE = (
    "https://script.google.com/macros/s/"
    "AKfycbxUJt9ClFvBQyum0AsoIy0Ve0dJkWBK6BvHlbYHiWAkQxhYMYJfZs0WEzOGJtp2unLJhA"
    "/exec?page="
)

CAPS_ANSWERS = [
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
assert len(CAPS_ANSWERS) == 60

# ── OPS LIMIT ANSWERS — txtGrdlimit_0 to 60 (61 fields) ─────────────────────────
# F-15SG aircraft operating limits. These are NUMBERS/text specific to the jet and
# are NOT yet filled in — replace each None with the real value before enabling the
# Ops Limit button (see the labels for what each index is). The form validates all
# 61 fields, so every entry must be set. Order matches txtGrdlimit_<index>.
OPSLIMIT_ANSWERS = [
    # ── ENGINE LIMITS table (GROUND EGT/RPM/OIL, FLIGHT EGT/RPM/OIL) ────────
    "935",  # 0  START   · GROUND EGT °C
    "935",  # 1  START   · FLIGHT EGT °C
    "650",  # 2  IDLE    · GROUND EGT °C
    "80",   # 3  IDLE    · GROUND RPM %
    "15",   # 4  IDLE    · GROUND OIL PSI (low)
    "65",   # 5  IDLE    · GROUND OIL PSI (high)
    "15",   # 6  IDLE    · FLIGHT OIL PSI (low)
    "65",   # 7  IDLE    · FLIGHT OIL PSI (high)
    "980",  # 8  MIL/AUG · GROUND EGT °C
    "108",  # 9  MIL/AUG · GROUND RPM %
    "35",   # 10 MIL/AUG · GROUND OIL PSI (low)
    "65",   # 11 MIL/AUG · GROUND OIL PSI (high)
    "980",  # 12 MIL/AUG · FLIGHT EGT °C
    "108",  # 13 MIL/AUG · FLIGHT RPM %
    "35",   # 14 MIL/AUG · FLIGHT OIL PSI (low)
    "65",   # 15 MIL/AUG · FLIGHT OIL PSI (high)
    "10",   # 16 FLUCT   · GROUND EGT ± °C
    "1",    # 17 FLUCT   · GROUND RPM ± %
    "5",    # 18 FLUCT   · GROUND OIL ± PSI
    "10",   # 19 FLUCT   · FLIGHT EGT ± °C
    "1",    # 20 FLUCT   · FLIGHT RPM ± %
    "5",    # 21 FLUCT   · FLIGHT OIL ± PSI

    # ── AIRSPEED / LOAD FACTOR table ────────────────────────────────────────
    "250",  # 22 LANDING GEAR (NORMAL) · airspeed KCAS
    "2",    # 23 LANDING GEAR (NORMAL) · load factor G
    "300",  # 24 Ldg gear spd raised to … KCAS
    "1.25", # 25 Load factor reduced to … G above 250 KCAS (step 0.01)
    "250",  # 26 LANDING GEAR (Emerg Ext) · airspeed KCAS
    "2",    # 27 LANDING GEAR (Emerg Ext) · load factor G
    "200",  # 28 Positional lights may not show 3 greens until … KCAS
    "250",  # 29 FLAPS DOWN · airspeed KCAS
    "0",    # 30 FLAPS DOWN · load factor from … G
    "4",    # 31 FLAPS DOWN · load factor to + … G
    "1",    # 32 INLETS EMERG POSITION · from … G
    "4",    # 33 INLETS EMERG POSITION · to + … G
    "60",   # 34 CANOPY OPEN · KNOTS
    "210",  # 35 TIRES (NOSE) · KNOTS
    "227",  # 36 TIRES (MAIN) · KNOTS

    # ── JFS ─────────────────────────────────────────────────────────────────
    "10",   # 37 Max sec between initiation and READY light
    "15",   # 38 … sec if below 0°F
    "90",   # 39 Max engagement time sec
    "150",  # 40 Extended to … sec if HOT START
    "20",   # 41 Wait … sec before re-engaging if engagement > 90 sec
    "10",   # 42 Min … sec between 1st eng at idle and 2nd eng engagement

    # ── MAX 30 CPU AOA conditions ───────────────────────────────────────────
    "8000",        # 43 Without ext tanks, lateral asymmetry over … ft-lbs
    "5000",        # 44 With ext tanks, lateral asymmetry over … ft-lbs
    "A/G",         # 45 … stores (text)
    "CARGO",       # 46 … pods (text)
    "35",          # 47 SUU-20B/A exception limited to … CPU AOA
    "FUEL",        # 48 … in wing mounted tanks (text)
    "3",           # 49 … external tanks
    "DOWN",        # 50 Gear … (text)
    "SPLIT",       # 51 … Ramps (text)
    "OFF",         # 52 CAS … (text)
    "HI AOA DGRD", # 53 … caution (text)
    "TANK 1",      # 54 … fuel transfer problem (text)

    # ── CROSSWIND LIMITS ────────────────────────────────────────────────────
    "30",          # 55 Dry … Kts
    "25",          # 56 Wet … Kts
    "1/2",         # 57 Effective wind velocity = steady + … gust velocity (text)
    "050/35",      # 58 Winds 050/30G40 → effective wind vel is … (text)

    # ── NEGATIVE G FLIGHT ───────────────────────────────────────────────────
    "7",           # 59 Negative G flight limited to … secs
    "FRONT",       # 60 Fuel migrates toward the … of the feed tank (text)
]
assert len(OPSLIMIT_ANSWERS) == 61

# Each form: page slug, answers, field-id prefix, the "check answers" button id,
# and the label that shows the check result.
FORMS = {
    "caps": {
        "url":       _BASE + "page2",
        "answers":   CAPS_ANSWERS,
        "prefix":    "txtCap_",
        "check_btn": "#btn_chkAnswer",
        "check_lbl": "#L_chkAnswer",
    },
    "opslimit": {
        "url":       _BASE + "opslimit",
        "answers":   OPSLIMIT_ANSWERS,
        "prefix":    "txtGrdlimit_",
        "check_btn": "#btn_limits1",
        "check_lbl": "#L_limits1",
    },
}

# ── PLAYWRIGHT LOGIC ──────────────────────────────────────────────────────────

async def submit_form(form_key: str, callsign: str) -> dict:
    cfg = FORMS[form_key]
    answers = cfg["answers"]

    if any(a is None for a in answers):
        return {
            "ok": False,
            "message": (
                f"The {form_key} answers are not configured yet "
                f"(fill in OPSLIMIT_ANSWERS in app.py)."
            ),
        }

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
            await page.goto(cfg["url"], wait_until="networkidle", timeout=60_000)

            sandbox = page.frame_locator("#sandboxFrame")
            form    = sandbox.frame_locator("#userHtmlFrame")

            await form.locator(f"#{cfg['prefix']}0").wait_for(state="visible", timeout=30_000)

            for i, answer in enumerate(answers):
                await form.locator(f"#{cfg['prefix']}{i}").fill(str(answer))

            await form.locator(cfg["check_btn"]).click()

            # Poll for the submit button to enable. The form only enables it once
            # every answer validates; on a mismatch it disables fields up to the
            # first wrong one and leaves that field enabled (so we can name it).
            enabled = False
            for _ in range(60):  # ~30 s
                if await form.locator("#btn_submit").is_enabled():
                    enabled = True
                    break
                await page.wait_for_timeout(500)

            if not enabled:
                try:
                    msg = (await form.locator(cfg["check_lbl"]).text_content(timeout=2_000) or "").strip()
                except Exception:
                    msg = ""
                bad = None
                for i in range(len(answers)):
                    try:
                        if await form.locator(f"#{cfg['prefix']}{i}").is_enabled():
                            bad = i
                            break
                    except Exception:
                        pass
                detail = (
                    f" First field still flagged: {cfg['prefix']}{bad} "
                    f"(value sent: {answers[bad]!r})." if bad is not None else ""
                )
                return {
                    "ok": False,
                    "message": f"Validation did not pass. Form said: {msg or '(no message)'}.{detail}",
                }

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

@app.route("/favicon.ico")
def favicon():
    # Browsers auto-request this; we have no icon, so answer "no content"
    # instead of letting it 404 and clutter the logs.
    return ("", 204)

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(force=True, silent=True) or {}
    callsign = (data.get("callsign") or "").strip()
    form_key = (data.get("form") or "caps").strip().lower()

    if not callsign:
        return jsonify({"ok": False, "message": "Callsign is required."}), 400
    if form_key not in FORMS:
        return jsonify({"ok": False, "message": f"Unknown form '{form_key}'."}), 400

    result = asyncio.run(submit_form(form_key, callsign))
    status = 200 if result["ok"] else 500
    return jsonify(result), status

# ── ENTRY ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
