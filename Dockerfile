# One service: FastAPI backend + the built React frontend (/, /walk, /didi) on the same origin.

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
RUN mkdir -p artifacts/waypoints artifacts/reports data/uploads

# Render sets $PORT; one worker keeps the in-process event feed and IVR callbacks together
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
