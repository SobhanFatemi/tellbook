FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 60 -r requirements.lock

COPY . .
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /app/media /app/private_media /app/staticfiles /app/beat \
    && chown -R app:app /app/media /app/private_media /app/staticfiles /app/beat
USER app

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
