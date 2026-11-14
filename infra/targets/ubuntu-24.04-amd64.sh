#!/usr/bin/env bash
# =============================================================================
#  TARGET: Ubuntu 24.04 LTS ("noble") on 64-bit Intel/AMD (amd64 / x86_64)
#
#  The usual cloud VM or PC server. Ubuntu 24.04 already ships Python 3.12 and
#  PostgreSQL 16, so nothing comes from a third-party package source.
#
#  Usage (from the repository root):
#      bash infra/targets/ubuntu-24.04-amd64.sh                 # plan only
#      bash infra/targets/ubuntu-24.04-amd64.sh apply           # do it
#      bash infra/targets/ubuntu-24.04-amd64.sh verify
#  Normally you run infra/install.sh, which picks this file for you.
# =============================================================================
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

IDRM_TARGET_ID="ubuntu-24.04-amd64"
IDRM_OS_ID="ubuntu"
IDRM_OS_VERSION="24.04"
IDRM_OS_CODENAME="noble"
IDRM_ARCH="amd64"

IDRM_PYTHON="python3.12"        # in Ubuntu's own archive
IDRM_PYTHON_PPA=""              # no extra package source needed
IDRM_PG_SOURCE="distro"         # PostgreSQL 16 + PostGIS are in Ubuntu's archive

# MinIO server binary for this hardware. Set IDRM_MINIO_URL before running to
# pin a specific release instead of the latest.
IDRM_MINIO_URL="${IDRM_MINIO_URL:-https://dl.min.io/server/minio/release/linux-amd64/minio}"

idrm_run "$@"
