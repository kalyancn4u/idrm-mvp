#!/usr/bin/env bash
# =============================================================================
#  infra/lib/common.sh — the few lines every target script shares.
#
#  This file is "sourced" (loaded) by the scripts in infra/targets/. It is not
#  run on its own.
#
#  A target script's whole job is to say WHAT IS DIFFERENT about one
#  operating-system / hardware pair, as IDRM_* variables, and then call
#  `idrm_run "$@"`. All the real work is in infra/idrm_infra.py.
# =============================================================================

# Stop at the first failing command, at any unset variable, and if any part
# of a pipeline fails.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export INFRA_DIR

idrm_die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# idrm_run <arguments for idrm_infra.py>
#   Exports the target description and hands over to the master script.
idrm_run() {
  # Never as root: the master script uses sudo for the commands that need it,
  # and prints each one first.
  [ "$(id -u)" -ne 0 ] || idrm_die "run as a normal user that can use sudo, not as root"

  command -v python3 >/dev/null 2>&1 \
    || idrm_die "python3 is missing. Install it with:  sudo apt-get install -y python3"

  # The master script needs Python 3.10+ (Ubuntu 22.04 and later have it).
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || idrm_die "python3 is older than 3.10"

  export IDRM_TARGET_ID IDRM_OS_ID IDRM_OS_VERSION IDRM_OS_CODENAME IDRM_ARCH \
         IDRM_PYTHON IDRM_PYTHON_PPA IDRM_PG_SOURCE IDRM_MINIO_URL

  # With no arguments, show the plan. Nothing changes until "apply".
  if [ "$#" -eq 0 ]; then set -- plan; fi

  exec python3 "${INFRA_DIR}/idrm_infra.py" "$@"
}
