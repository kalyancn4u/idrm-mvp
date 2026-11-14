#!/usr/bin/env bash
# =============================================================================
#  TARGET: Ubuntu 22.04 LTS ("jammy") on 64-bit ARM (arm64 / aarch64)
#
#  The older LTS on ARM hardware. Like ubuntu-22.04-amd64 it adds Python 3.11
#  (deadsnakes PPA) and PostgreSQL 16 (apt.postgresql.org) from outside
#  Ubuntu's own archive — read the notes in that file. The only other
#  difference is the MinIO binary.
#
#  Usage (from the repository root):
#      bash infra/targets/ubuntu-22.04-arm64.sh                 # plan only
#      bash infra/targets/ubuntu-22.04-arm64.sh apply           # do it
#  Normally you run infra/install.sh, which picks this file for you.
# =============================================================================
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

IDRM_TARGET_ID="ubuntu-22.04-arm64"
IDRM_OS_ID="ubuntu"
IDRM_OS_VERSION="22.04"
IDRM_OS_CODENAME="jammy"
IDRM_ARCH="arm64"

IDRM_PYTHON="python3.11"
IDRM_PYTHON_PPA="ppa:deadsnakes/ppa"
IDRM_PG_SOURCE="pgdg"

IDRM_MINIO_URL="${IDRM_MINIO_URL:-https://dl.min.io/server/minio/release/linux-arm64/minio}"

idrm_run "$@"
