#!/usr/bin/env bash
# =============================================================================
#  TARGET: Ubuntu 24.04 LTS ("noble") on 64-bit ARM (arm64 / aarch64)
#
#  ARM cloud servers (AWS Graviton, Ampere, Oracle Ampere A1) and boards such
#  as Raspberry Pi 4/5 running 64-bit Ubuntu. Same as the amd64 target except
#  for the MinIO binary, which is built per processor type.
#
#  Usage (from the repository root):
#      bash infra/targets/ubuntu-24.04-arm64.sh                 # plan only
#      bash infra/targets/ubuntu-24.04-arm64.sh apply           # do it
#  Normally you run infra/install.sh, which picks this file for you.
# =============================================================================
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

IDRM_TARGET_ID="ubuntu-24.04-arm64"
IDRM_OS_ID="ubuntu"
IDRM_OS_VERSION="24.04"
IDRM_OS_CODENAME="noble"
IDRM_ARCH="arm64"

IDRM_PYTHON="python3.12"
IDRM_PYTHON_PPA=""
IDRM_PG_SOURCE="distro"

IDRM_MINIO_URL="${IDRM_MINIO_URL:-https://dl.min.io/server/minio/release/linux-arm64/minio}"

idrm_run "$@"
