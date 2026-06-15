#!/usr/bin/env bash
# Preflight check for `make demo`. Verifies required tools, system
# resources, and host ports before the docker/seed pipeline runs.
#
# Designed to work on a bare VM where only `bash` is installed (no make,
# no docker yet). Avoids Bash 4+ features so it runs on macOS' system
# Bash 3.2. Does not read .env or any credentials.
#
# Exit codes:
#   0 — all required checks passed (warnings OK)
#   1 — one or more required checks failed

# Intentionally not using `set -e`: a failing check must not abort the
# script before we print the summary. `set -u` would also be hostile to
# the optional probes below.

OS="$(uname -s 2>/dev/null || echo unknown)"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

# Colors only when stdout is a tty and NO_COLOR is unset.
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'
  C_BOLD=$'\033[1m'
  C_RESET=$'\033[0m'
else
  C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""; C_RESET=""
fi

LABEL_WIDTH=16

# --- Output helpers --------------------------------------------------------

header() {
  printf '\n%s=== %s ===%s\n' "${C_BOLD}" "$1" "${C_RESET}"
}

# pad LABEL to LABEL_WIDTH columns (right-padded with spaces).
pad() {
  printf '%-*s' "${LABEL_WIDTH}" "$1"
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '[%s✓%s] %s %s\n' "${C_GREEN}" "${C_RESET}" "$(pad "$1")" "$2"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '[%s!%s] %s %s\n' "${C_YELLOW}" "${C_RESET}" "$(pad "$1")" "$2"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '[%s✗%s] %s %s\n' "${C_RED}" "${C_RESET}" "$(pad "$1")" "$2"
}

# --- OS-specific install hint ---------------------------------------------

# install_hint <tool> -> prints "install with: ..." (no trailing newline)
install_hint() {
  tool="$1"
  case "${OS}" in
    Darwin)
      if [ "${tool}" = "docker" ] || [ "${tool}" = "docker compose" ]; then
        printf 'install Docker Desktop from https://docker.com/products/docker-desktop'
      else
        printf 'install with: brew install %s' "${tool}"
      fi
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        if [ "${tool}" = "docker" ] || [ "${tool}" = "docker compose" ]; then
          printf 'install Docker Engine: https://docs.docker.com/engine/install/ubuntu/'
        else
          printf 'install with: sudo apt-get install -y %s' "${tool}"
        fi
      elif command -v dnf >/dev/null 2>&1; then
        if [ "${tool}" = "docker" ] || [ "${tool}" = "docker compose" ]; then
          printf 'install Docker Engine: https://docs.docker.com/engine/install/'
        else
          printf 'install with: sudo dnf install -y %s' "${tool}"
        fi
      elif command -v yum >/dev/null 2>&1; then
        if [ "${tool}" = "docker" ] || [ "${tool}" = "docker compose" ]; then
          printf 'install Docker Engine: https://docs.docker.com/engine/install/'
        else
          printf 'install with: sudo yum install -y %s' "${tool}"
        fi
      else
        printf 'install %s via your package manager' "${tool}"
      fi
      ;;
    *)
      printf 'install %s via your package manager' "${tool}"
      ;;
  esac
}

fail_missing_tool() {
  fail "$1" "not found — $(install_hint "$1")"
}

# --- Required tools --------------------------------------------------------

check_bash_version() {
  # BASH_VERSINFO is set even on macOS Bash 3.2.
  major="${BASH_VERSINFO[0]:-0}"
  minor="${BASH_VERSINFO[1]:-0}"
  ver="${BASH_VERSION:-unknown}"
  if [ "${major}" -gt 3 ] || { [ "${major}" -eq 3 ] && [ "${minor}" -ge 2 ]; }; then
    pass "bash" "v${ver}"
  else
    fail "bash" "v${ver} (need >= 3.2) — $(install_hint bash)"
  fi
}

check_simple_tool() {
  name="$1"
  version_arg="${2:---version}"
  if command -v "${name}" >/dev/null 2>&1; then
    ver="$("${name}" ${version_arg} 2>&1 | head -n 1)"
    pass "${name}" "${ver}"
  else
    fail_missing_tool "${name}"
  fi
}

check_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    fail_missing_tool "docker"
    return
  fi
  ver="$(docker --version 2>&1 | head -n 1)"
  pass "docker" "${ver}"
}

check_docker_compose_v2() {
  if ! command -v docker >/dev/null 2>&1; then
    # Already reported by check_docker; report compose unavailable too.
    fail "docker compose" "docker CLI missing — $(install_hint 'docker compose')"
    return
  fi
  if docker compose version >/dev/null 2>&1; then
    ver="$(docker compose version 2>&1 | head -n 1)"
    pass "docker compose" "${ver}"
  else
    fail "docker compose" "v2 plugin not found — $(install_hint 'docker compose')"
  fi
}

check_docker_daemon() {
  if ! command -v docker >/dev/null 2>&1; then
    fail "docker daemon" "docker CLI missing"
    return
  fi
  if docker info >/dev/null 2>&1; then
    pass "docker daemon" "reachable"
  else
    fail "docker daemon" "not reachable — start Docker Desktop / dockerd"
  fi
}

# --- System resources ------------------------------------------------------

# free disk space on the working tree filesystem, in GB (integer).
disk_free_gb() {
  # `df -k .` prints 1K blocks; column 4 = available. Skip the header
  # and any "Filesystem" wrapped line by taking the last line.
  line="$(df -k . 2>/dev/null | awk 'NR>1' | tail -n 1)"
  if [ -z "${line}" ]; then
    echo ""
    return
  fi
  # Available KB is the 4th numeric field; on some systems the
  # filesystem name wraps, but `tail -n 1` already collapses that.
  kb="$(echo "${line}" | awk '{print $4}')"
  case "${kb}" in
    ''|*[!0-9]*) echo ""; return ;;
  esac
  echo $((kb / 1024 / 1024))
}

check_disk() {
  gb="$(disk_free_gb)"
  if [ -z "${gb}" ]; then
    warn "disk" "could not determine free space"
    return
  fi
  if [ "${gb}" -lt 5 ]; then
    fail "disk" "${gb} GB free (minimum: 5 GB)"
  elif [ "${gb}" -lt 10 ]; then
    warn "disk" "${gb} GB free (recommended: 10 GB)"
  else
    pass "disk" "${gb} GB free"
  fi
}

mem_total_gb() {
  case "${OS}" in
    Darwin)
      bytes="$(sysctl -n hw.memsize 2>/dev/null)"
      ;;
    Linux)
      # MemTotal is in kB.
      kb="$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo 2>/dev/null)"
      if [ -n "${kb}" ]; then
        bytes=$((kb * 1024))
      else
        bytes=""
      fi
      ;;
    *)
      bytes=""
      ;;
  esac
  case "${bytes}" in
    ''|*[!0-9]*) echo ""; return ;;
  esac
  # Convert to GB (integer, rounded down).
  echo $((bytes / 1024 / 1024 / 1024))
}

check_memory() {
  gb="$(mem_total_gb)"
  if [ -z "${gb}" ]; then
    warn "memory" "could not determine total RAM on ${OS}"
    return
  fi
  if [ "${gb}" -lt 4 ]; then
    fail "memory" "${gb} GB total (minimum: 4 GB)"
  elif [ "${gb}" -lt 8 ]; then
    warn "memory" "${gb} GB total (recommended: 8 GB)"
  else
    pass "memory" "${gb} GB total"
  fi
}

cpu_count() {
  case "${OS}" in
    Darwin)
      sysctl -n hw.ncpu 2>/dev/null
      ;;
    Linux)
      if command -v nproc >/dev/null 2>&1; then
        nproc 2>/dev/null
      else
        grep -c '^processor' /proc/cpuinfo 2>/dev/null
      fi
      ;;
    *)
      echo ""
      ;;
  esac
}

check_cpu() {
  n="$(cpu_count)"
  case "${n}" in
    ''|*[!0-9]*)
      warn "cpu" "could not determine core count on ${OS}"
      return
      ;;
  esac
  if [ "${n}" -lt 2 ]; then
    warn "cpu" "${n} core (recommended: 2+)"
  else
    pass "cpu" "${n} cores"
  fi
}

# --- Ports -----------------------------------------------------------------

# Probe selected once on first port check. Values: lsof | ss | none.
PORT_PROBE=""

detect_port_probe() {
  if [ -n "${PORT_PROBE}" ]; then
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    PORT_PROBE="lsof"
  elif command -v ss >/dev/null 2>&1; then
    PORT_PROBE="ss"
  else
    PORT_PROBE="none"
    warn "ports" "neither lsof nor ss available — skipping port checks"
  fi
}

port_in_use_lsof() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

port_in_use_ss() {
  ss -tln "sport = :$1" 2>/dev/null | grep -q LISTEN
}

check_port() {
  port="$1"
  label="$2"
  detect_port_probe
  case "${PORT_PROBE}" in
    lsof)
      if port_in_use_lsof "${port}"; then
        warn "port ${port}" "in use (${label}) — stop the conflicting service or change the port"
      else
        pass "port ${port}" "free (${label})"
      fi
      ;;
    ss)
      if port_in_use_ss "${port}"; then
        warn "port ${port}" "in use (${label}) — stop the conflicting service or change the port"
      else
        pass "port ${port}" "free (${label})"
      fi
      ;;
    *)
      warn "port ${port}" "skipping ${label} check (no probe available)"
      ;;
  esac
}

# --- Run all checks --------------------------------------------------------

printf '%sdoctor.sh — preflight for make demo%s  (os: %s)\n' "${C_BOLD}" "${C_RESET}" "${OS}"

header "Required tools"
check_bash_version
check_docker
check_docker_compose_v2
check_docker_daemon
check_simple_tool make
check_simple_tool git
check_simple_tool curl

header "System resources"
check_disk
check_memory
check_cpu

header "Ports"
check_port 6379 "Redis"
check_port 8000 "backend"
check_port 5173 "frontend-dev"
check_port 8001 "RedisInsight"

# --- Summary ---------------------------------------------------------------

header "Summary"
printf '  passed:   %s%d%s\n' "${C_GREEN}" "${PASS_COUNT}" "${C_RESET}"
printf '  warnings: %s%d%s\n' "${C_YELLOW}" "${WARN_COUNT}" "${C_RESET}"
printf '  failed:   %s%d%s\n' "${C_RED}" "${FAIL_COUNT}" "${C_RESET}"

if [ "${FAIL_COUNT}" -gt 0 ]; then
  printf '\n%sverdict: NOT READY%s — fix the failed checks above, then rerun.\n' "${C_RED}" "${C_RESET}"
  printf '         set SKIP_DOCTOR=1 to bypass (not recommended).\n'
  exit 1
fi

if [ "${WARN_COUNT}" -gt 0 ]; then
  printf '\n%sverdict: READY (with warnings)%s\n' "${C_YELLOW}" "${C_RESET}"
else
  printf '\n%sverdict: READY%s\n' "${C_GREEN}" "${C_RESET}"
fi
exit 0
