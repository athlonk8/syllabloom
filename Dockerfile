FROM node:24-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS application

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SYLLABLOOM_DATA_DIR=/data \
    SYLLABLOOM_FRONTEND_DIST=/app/frontend-dist

WORKDIR /app
COPY backend/requirements.txt ./
RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ /app/
COPY --from=frontend-build /frontend/dist /app/frontend-dist

RUN mkdir -p /data
EXPOSE 8000

CMD ["sh", "-c", "python -m app.migrations && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
