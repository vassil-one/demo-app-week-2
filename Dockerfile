# Dockerfile — multi-stage, cache-friendly, non-root. End-of-Week-1 state.

# ---- build stage: install dependencies into /install ----
FROM python:3.12-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage: only what is needed to run ----
FROM python:3.12-slim
ARG APP_VERSION=v1
ENV APP_VERSION=${APP_VERSION}
WORKDIR /app
COPY --from=build /install /usr/local
COPY app/ ./app/
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
