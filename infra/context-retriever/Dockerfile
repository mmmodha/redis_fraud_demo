# Context Retriever bootstrap image.
#
# One-shot container: provisions the demo's context surface, mints an agent
# key, and writes both back to the host's mounted .env file. Keeps the
# Python 3.11+ requirement (for redis-context-retriever / ctxctl) out of the
# presenter's host environment.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /work

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Bootstrap script is mounted from infra/context-retriever at run time so
# edits don't require a rebuild; we still COPY a default copy so the image
# is self-contained when used outside of `make context-up`.
COPY bootstrap.py /work/bootstrap.py

ENTRYPOINT ["python", "/work/bootstrap.py"]
