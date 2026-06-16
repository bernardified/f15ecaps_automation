# Official Playwright Python image — Chromium is pre-installed, no extra steps needed.
# This tag MUST match the pinned playwright version in requirements.txt, otherwise the
# pip-installed driver looks for a browser binary this image doesn't carry.
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
