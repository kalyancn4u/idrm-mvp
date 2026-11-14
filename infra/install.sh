#!/usr/bin/env bash
# =============================================================================
#  infra/install.sh — the one command to remember.
#
#  It looks at this machine (which operating system, which version, which
#  processor type), picks the matching script in infra/targets/, and runs it.
#  If there is no script for this machine it STOPS — it never guesses.
#
#      bash infra/install.sh                 show the plan; change nothing
#      bash infra/install.sh apply           carry it out (asks first)
#      bash infra/install.sh verify          health report
#      bash infra/install.sh detect          just say what this machine is
#
#  Options go after the command and are passed through, for example:
#      bash infra/install.sh apply --profile production --domain idrm.example.org --with-firewall
#      bash infra/install.sh apply --only code --only services      # deploy new code
#
#  Full guide: docs/infra/INFRASTRUCTURE-MASTER-PLAN.md
# =============================================================================
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ "$(uname -s)" = "Linux" ] || {
  echo "error: this installer is for Ubuntu servers. This machine is $(uname -s)." >&2
  echo "       For a development laptop use Docker instead: see section 4 of the master plan." >&2
  exit 1
}
[ -r /etc/os-release ] || { echo "error: /etc/os-release not found — cannot tell which Linux this is" >&2; exit 1; }

# /etc/os-release is a list of NAME=value lines describing the system.
# shellcheck disable=SC1091
. /etc/os-release

case "$(uname -m)" in
  x86_64)          arch="amd64" ;;
  aarch64 | arm64) arch="arm64" ;;
  *)               arch="$(uname -m)" ;;
esac

target="${ID:-unknown}-${VERSION_ID:-unknown}-${arch}"
script="${INFRA_DIR}/targets/${target}.sh"

if [ ! -f "$script" ]; then
  echo "error: no target script for this machine: ${target}" >&2
  echo "       supported targets:" >&2
  for f in "${INFRA_DIR}"/targets/*.sh; do echo "         - $(basename "$f" .sh)" >&2; done
  echo "       To support a new machine, copy the closest file in infra/targets/ and adjust it." >&2
  exit 1
fi

echo "machine: ${target}"
exec bash "$script" "$@"
