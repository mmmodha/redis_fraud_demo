#!/usr/bin/env bash
# scripts/audit.sh — secrets audit via gitleaks in Docker.
#
# Scans BOTH the working tree and the FULL git history for leaked
# secrets using zricethezav/gitleaks. The host does not need gitleaks
# installed — only Docker.
#
# Exit codes:
#   0  no findings
#   1  one or more findings (a redacted report is still produced)
#   2  pre-flight error (missing docker)
#
# Hard rule: this script NEVER prints raw secret values. The raw JSON
# reports written by gitleaks are deleted after a redacted summary
# (first-4/last-4 of each match) is produced.

set -uo pipefail

IMAGE="zricethezav/gitleaks:latest"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${REPO_ROOT}/.audit"
SUMMARY="${OUT_DIR}/audit-report.txt"

mkdir -p "${OUT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker not found on PATH. Install Docker Desktop and retry." >&2
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  echo "error: git not found on PATH." >&2
  exit 2
fi

# Pre-pull (no-op if already cached). Silence the digest line.
docker pull --quiet "${IMAGE}" >/dev/null

# Snapshot only tracked files into a temp dir so the working-tree scan
# does NOT flag gitignored files (e.g. the developer's local `.env` or
# Next.js .next/ build artefacts). `git ls-files` includes modified
# tracked files, so unstaged edits are still audited.
TMP_TREE="$(mktemp -d -t gitleaks-tree.XXXXXX)"
cleanup() { rm -rf "${TMP_TREE}"; }
trap cleanup EXIT

# Filter `git ls-files` through an existence check so tracked-but-locally-
# missing files (a common state after a stale Playwright run) don't spam
# tar errors and don't fail the script.
(
  cd "${REPO_ROOT}"
  git ls-files -z | while IFS= read -r -d '' f; do
    [ -e "$f" ] && printf '%s\0' "$f"
  done | tar --null -T - -cf -
) | tar -xf - -C "${TMP_TREE}"

# When the repo is a git worktree, `.git` is a file pointing at a
# directory inside the parent repo's common .git dir. The container
# needs that common dir mounted at the SAME absolute path so gitleaks
# can resolve refs and walk history.
GIT_COMMON_DIR="$(cd "$(git -C "${REPO_ROOT}" rev-parse --git-common-dir)" && pwd)"
HISTORY_EXTRA_MOUNTS=()
if [ "${GIT_COMMON_DIR}" != "${REPO_ROOT}/.git" ]; then
  HISTORY_EXTRA_MOUNTS=(-v "${GIT_COMMON_DIR}:${GIT_COMMON_DIR}:ro")
fi

echo "==> gitleaks: scanning working tree (tracked files only)…"
docker run --rm \
  -v "${TMP_TREE}:/repo:ro" \
  -v "${OUT_DIR}:/report" \
  -w /repo \
  "${IMAGE}" detect \
  --no-banner \
  --no-git \
  --source=/repo \
  --report-format=json \
  --report-path=/report/gitleaks-workdir.json
WORKDIR_EXIT=$?

echo "==> gitleaks: scanning full git history (all refs)…"
docker run --rm \
  -v "${REPO_ROOT}:/repo:ro" \
  -v "${OUT_DIR}:/report" \
  ${HISTORY_EXTRA_MOUNTS[@]+"${HISTORY_EXTRA_MOUNTS[@]}"} \
  -w /repo \
  "${IMAGE}" detect \
  --no-banner \
  --source=/repo \
  --log-opts=--all \
  --report-format=json \
  --report-path=/report/gitleaks-history.json
HISTORY_EXIT=$?

# Produce a redacted human-readable summary, then DELETE the raw JSON
# reports so secret values do not linger on disk.
python3 - "${OUT_DIR}/gitleaks-workdir.json" \
              "${OUT_DIR}/gitleaks-history.json" \
              "${SUMMARY}" <<'PY'
import json, os, sys, pathlib

def redact(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "*" * len(value) + f" (len={len(value)})"
    return f"{value[:4]}…{value[-4:]} (len={len(value)})"

def load(path: str):
    p = pathlib.Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []

workdir_path, history_path, out_path = sys.argv[1:4]
workdir = load(workdir_path)
history = load(history_path)

lines = []
lines.append("Gitleaks secrets audit — REDACTED report")
lines.append("=" * 60)
lines.append(f"Working tree findings : {len(workdir)}")
lines.append(f"Git history findings  : {len(history)}")
lines.append("")

def fmt(findings, label):
    out = [f"--- {label} ---"]
    if not findings:
        out.append("(none)")
        out.append("")
        return out
    for i, f in enumerate(findings, 1):
        out.append(f"[{i}] rule        : {f.get('RuleID', '?')}")
        out.append(f"    file        : {f.get('File', '?')}")
        if f.get("StartLine"):
            out.append(f"    line        : {f.get('StartLine')}")
        if f.get("Commit"):
            out.append(f"    commit      : {f.get('Commit', '?')[:12]}")
            out.append(f"    author      : {f.get('Author', '?')}")
            out.append(f"    date        : {f.get('Date', '?')}")
        secret = f.get("Secret") or f.get("Match", "")
        out.append(f"    redacted    : {redact(secret)}")
        out.append("")
    return out

lines += fmt(workdir, "Working tree")
lines += fmt(history, "Git history")

for raw in (workdir_path, history_path):
    try:
        os.remove(raw)
    except OSError:
        pass

text = "\n".join(lines)
pathlib.Path(out_path).write_text(text)
print(text)
PY

if [ "${WORKDIR_EXIT}" -ne 0 ] || [ "${HISTORY_EXIT}" -ne 0 ]; then
  echo ""
  echo "FAIL: gitleaks reported findings. Redacted summary above and at"
  echo "      ${SUMMARY}. Raw JSON reports were deleted."
  echo "      Rotate any confirmed secrets BEFORE rewriting history."
  echo "      History rewrites (git filter-repo / BFG) require a"
  echo "      separate, explicitly approved task — do NOT run them here."
  exit 1
fi

echo ""
echo "OK: no secrets found in working tree or git history."
exit 0
