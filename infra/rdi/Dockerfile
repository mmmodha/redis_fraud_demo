FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY processor.py triggers.sql ./

ENV PYTHONUNBUFFERED=1 \
    RDI_CONFIG_DIR=/etc/rdi/config

CMD ["python", "-u", "processor.py"]
