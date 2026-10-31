# FastAPI backend + the built React frontend (/, /walk, /didi) on one origin. Deployed on AWS EC2
# behind Caddy (deploy/aws); Vercel can also serve the pages and forward /api and /uploads here.

FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/ backend/
COPY data/ data/
COPY frontend/public/ frontend/public/
COPY --from=web /app/frontend/dist frontend/dist
RUN mkdir -p artifacts/waypoints artifacts/reports data/uploads /var/lib/fasalnetra  && useradd -m -u 1000 user && chown -R user /app /var/lib/fasalnetra
# Runs as uid 1000. On a server, mount a volume at /var/lib/fasalnetra and point DATABASE_URL / UPLOAD_DIR there
# so data survives rebuilds; otherwise SQLite and uploads live under /app/data.
USER user

# Spaces route to 7860 (README app_port); Render sets $PORT. One worker keeps the
# in-process event log and the missed-call callback timer together.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
