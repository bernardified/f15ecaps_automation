# 142 SQN e-CAPS / Ops Limit auto-submitter

Web tool that auto-fills and submits the squadron's weekly **CAPS** and monthly
**Ops Limit** Google-Apps-Script forms via headless Playwright, hosted on Railway.

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask web server. `GET /` serves the form; `POST /submit {callsign, form}` runs the Playwright submission. Config-driven via `FORMS` (`caps`, `opslimit`). |
| `submit_job.py` | One-shot CLI submitter for scheduled runs: `python submit_job.py <caps\|opslimit> [CALLSIGN]`. Reuses `submit_form()`; no web server needed. |
| `index.html` | Frontend — **Submit CAPS** / **Submit Ops Limit** buttons. |
| `Dockerfile` | Microsoft Playwright image (Chromium pre-installed). Tag **must** match `playwright==` in `requirements.txt`. |
| `requirements.txt` | `flask`, `playwright` (pinned to the Docker image version). |
| `ecaps_submit.py` | Original standalone local script (unchanged). |

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium      # only needed outside the Docker image
python app.py                    # web UI at http://localhost:5000
python submit_job.py caps CABLE  # one-shot CAPS submission
```

## Deploy (Railway)

1. Push to GitHub.
2. railway.app → New Project → Deploy from GitHub repo → this repo.
3. Railway detects the `Dockerfile` and builds.
4. Service → Settings → Networking → **Generate Domain**.
5. Open the URL — the form appears. `PORT` is read automatically.

## Scheduled submissions (Railway cron)

Railway cron runs a service's start command to completion, so the always-on web
service can't double as a cron job. Add **two more services** in the same project,
both deploying from this repo (same Docker image), each with a custom start
command and a cron schedule. **Railway cron is UTC**; the schedules below are
Singapore time (UTC+8) converted to UTC.

| Service | Start command | Cron (UTC) | Fires (SGT) |
|---|---|---|---|
| `caps-weekly` | `python submit_job.py caps CABLE` | `0 1 * * 0` | Sun 09:00 |
| `opslimit-monthly` | `python submit_job.py opslimit CABLE` | `0 1 30 * *` | 30th 09:00 |

For each: New Service → from this repo → Settings → **Custom Start Command** (above)
→ Settings → **Cron Schedule** (above). Results print to that service's logs
(`[OK]` / `[FAIL]`).

**Caveat — the 30th:** February has no 30th, so `opslimit-monthly` is skipped in
February. Use `0 1 28 * *` (28th) if a February run is required.
