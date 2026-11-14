#!/usr/bin/env bash
# =============================================================================
#  TARGET: Ubuntu 22.04 LTS ("jammy") on 64-bit Intel/AMD (amd64 / x86_64)
#
#  The older LTS. Two things it does NOT ship, which this target adds from
#  outside Ubuntu's own archive — know that you are trusting these sources:
#
#    * Python 3.11  — Ubuntu 22.04 has 3.10; the app needs 3.11 or newer.
#                     Source: the "deadsnakes" PPA (a community package source).
#    * PostgreSQL 16 — Ubuntu 22.04 has 14.
#                     Source: apt.postgresql.org (the PostgreSQL project's own
#                     repository). Its signing key is checked against a known
#                     fingerprint before it is trusted.
#
#  If you can choose, prefer Ubuntu 24.04: it needs neither.
#
#  Usage (from the repository root):
#      bash infra/targets/ubuntu-22.04-amd64.sh                 # plan only
#      bash infra/targets/ubuntu-22.04-amd64.sh apply           # do it
#  Normally you run infra/install.sh, which picks this file for you.
# =============================================================================
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

IDRM_TARGET_ID="ubuntu-22.04-amd64"
IDRM_OS_ID="ubuntu"
IDRM_OS_VERSION="22.04"
IDRM_OS_CODENAME="jammy"
IDRM_ARCH="amd64"

IDRM_PYTHON="python3.11"
IDRM_PYTHON_PPA="ppa:deadsnakes/ppa"
IDRM_PG_SOURCE="pgdg"

IDRM_MINIO_URL="${IDRM_MINIO_URL:-https://dl.min.io/server/minio/release/linux-amd64/minio}"

idrm_run "$@"
