FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    OMP_NUM_THREADS=4

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && find /usr/local/lib/python3.11 -name '__pycache__' -type d -prune -exec rm -rf {} +

COPY app/ /app/

RUN mkdir -p /data /models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
