# One-shot seeder image used by `make demo` to populate Postgres + Redis
# without any host-side pip/venv. Built from the repo root so it can pull
# both `data/requirements.txt` and the `data/` package in one layer.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY data/requirements.txt /tmp/data-requirements.txt
RUN pip install --no-cache-dir -r /tmp/data-requirements.txt "redis>=5,<6"

COPY data /app/data

# Default to the bank schema + transactions seed. `docker compose run`
# overrides with `python -m data.seed_memory` for the Redis pass.
CMD ["python", "-m", "data.seed"]
