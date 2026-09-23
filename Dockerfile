FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Aucune dépendance système : psycopg2-binary et les autres paquets
# s'installent depuis des wheels précompilés (image plus légère, build plus
# rapide et sans accès aux dépôts Debian).
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=4)" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
