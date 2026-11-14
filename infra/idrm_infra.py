#!/usr/bin/env python3
"""
IDRM infrastructure installer — the master script.

    python3 infra/idrm_infra.py detect               what machine is this?
    python3 infra/idrm_infra.py plan                 what WOULD be done (changes nothing)
    python3 infra/idrm_infra.py apply                do it (asks first)
    python3 infra/idrm_infra.py verify               is the result healthy?

Normally you do not call this file yourself: `infra/install.sh` picks the
right target script for your machine, and that script calls this one.

HOW IT WORKS — read this first
------------------------------
The whole install is a list of STEPS (see `build_steps`). Every step has two
halves:

    check()   looks at the machine and answers "is this already done?"
              It never changes anything.
    apply()   does the work. Only called when check() said "no".

Because of that split, running the installer twice is safe: the second run
finds everything done and changes nothing. That property is called
IDEMPOTENCE, and it is also what makes an "incremental patch" possible —
add a step, run again, and only the new step runs.

Safety rules built in
---------------------
  * `plan` is the default mind-set: nothing is changed until `apply`.
  * Run as a normal user. Commands that need root are run through `sudo`,
    one at a time, and each is printed before it runs.
  * Passwords are generated here, written once to /etc/idrm/idrm.env
    (readable by root and the `idrm` service user only) and never printed.
  * An existing secrets file is never regenerated — only missing keys are added.
  * Any config file is copied to `<name>.bak-<time>` before it is replaced.
  * The database, Redis, MinIO and both apps listen on 127.0.0.1 only.
  * No `curl | bash`. Downloads are checked (key fingerprint / SHA-256).
  * The target script must match the real machine, or the run stops.

Needs only the Python standard library, version 3.10 or newer (Ubuntu 22.04
ships 3.10).
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import os
import platform
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ----------------------------------------------------------------------------
# Fixed facts about the installation
# ----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

SERVICE_USER = "idrm"
APP_DIR = Path("/opt/idrm/app")          # a copy of this repository
VENV_DIR = Path("/opt/idrm/venv")        # the Python virtual environment
ETC_DIR = Path("/etc/idrm")              # configuration and secrets
ENV_FILE = ETC_DIR / "idrm.env"
KEYS_DIR = ETC_DIR / "keys"
DATA_DIR = Path("/var/lib/idrm")
MINIO_DATA = DATA_DIR / "minio"

DB_NAME = "idrm_db"
DB_USER = "idrm_user"
PG_VERSION = "16"

API_PORT = 8000
DASH_PORT = 5000
MINIO_PORT = 9000

# The PostgreSQL project's package-signing key. The downloaded key must have
# exactly this fingerprint, otherwise the repository is not added.
PGDG_KEY_URL = "https://www.postgresql.org/media/keys/ACCC4CF8.asc"
PGDG_KEY_FINGERPRINT = "B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8"
PGDG_KEYRING = Path("/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc")

PROFILES = ("dev", "staging", "production")

LOG_DIR = Path.home() / ".local" / "state" / "idrm-infra"


# ----------------------------------------------------------------------------
# Output helpers
# ----------------------------------------------------------------------------
_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


class Log:
    """Prints to the screen and appends the same lines (no colours) to a log file."""

    def __init__(self) -> None:
        self.file = None
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            self.path = LOG_DIR / f"run-{stamp}.log"
            self.file = open(self.path, "a", encoding="utf-8")
        except OSError:
            self.path = None

    def _write(self, plain: str) -> None:
        if self.file:
            self.file.write(plain + "\n")
            self.file.flush()

    def info(self, msg: str) -> None:
        print(f"  {msg}"); self._write(f"  {msg}")

    def ok(self, msg: str) -> None:
        print(_c("32", f"  ✓ {msg}")); self._write(f"  OK   {msg}")

    def todo(self, msg: str) -> None:
        print(_c("33", f"  → {msg}")); self._write(f"  TODO {msg}")

    def warn(self, msg: str) -> None:
        print(_c("33", f"  ! {msg}")); self._write(f"  WARN {msg}")

    def err(self, msg: str) -> None:
        print(_c("31", f"  ✗ {msg}"), file=sys.stderr); self._write(f"  ERR  {msg}")

    def head(self, msg: str) -> None:
        print(_c("1;36", f"\n▶ {msg}")); self._write(f"\n== {msg}")

    def cmd(self, msg: str) -> None:
        print(_c("2", f"    $ {msg}")); self._write(f"    $ {msg}")


class InstallError(Exception):
    """A step failed in a way the operator has to look at."""


# ----------------------------------------------------------------------------
# The machine we are on, and the target we were told to build for
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Target:
    """
    One operating-system / hardware pair. The values come from environment
    variables exported by a script in `infra/targets/` — that is where the
    differences between machines are written down, one small file per pair.
    """

    id: str             # e.g. "ubuntu-24.04-amd64"
    os_id: str          # "ubuntu"
    os_version: str     # "24.04"
    codename: str       # "noble"
    arch: str           # "amd64" | "arm64"   (Debian naming)
    python: str         # interpreter the app runs on, e.g. "python3.12"
    python_ppa: str     # "" or a PPA that provides that interpreter
    pg_source: str      # "distro" (Ubuntu ships PostgreSQL 16) | "pgdg"
    minio_url: str      # download URL of the MinIO server binary for this arch

    @staticmethod
    def from_env() -> "Target":
        def need(name: str) -> str:
            value = os.environ.get(name, "")
            if not value:
                raise InstallError(
                    f"{name} is not set. Do not run idrm_infra.py directly — "
                    f"use infra/install.sh, or a script in infra/targets/."
                )
            return value

        return Target(
            id=need("IDRM_TARGET_ID"),
            os_id=need("IDRM_OS_ID"),
            os_version=need("IDRM_OS_VERSION"),
            codename=need("IDRM_OS_CODENAME"),
            arch=need("IDRM_ARCH"),
            python=need("IDRM_PYTHON"),
            python_ppa=os.environ.get("IDRM_PYTHON_PPA", ""),
            pg_source=need("IDRM_PG_SOURCE"),
            minio_url=need("IDRM_MINIO_URL"),
        )


def read_os_release() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                out[key] = value.strip().strip('"')
    except OSError:
        pass
    return out


def machine_arch() -> str:
    """Hardware name in Debian's vocabulary."""
    return {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )


def describe_machine() -> dict[str, str]:
    rel = read_os_release()
    mem_kb = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                mem_kb = int(line.split()[1])
    except OSError:
        pass
    try:
        free_gb = shutil.disk_usage("/").free / 1e9
    except OSError:
        free_gb = 0.0
    return {
        "system": platform.system(),
        "os_id": rel.get("ID", "unknown"),
        "os_version": rel.get("VERSION_ID", "unknown"),
        "codename": rel.get("VERSION_CODENAME", "unknown"),
        "arch": machine_arch(),
        "memory_gb": f"{mem_kb / 1e6:.1f}",
        "disk_free_gb": f"{free_gb:.1f}",
        "wsl": "yes" if "microsoft" in platform.release().lower() else "no",
        "python": platform.python_version(),
        "user": getpass.getuser(),
    }


# ----------------------------------------------------------------------------
# Context: everything a step needs
# ----------------------------------------------------------------------------
@dataclass
class Ctx:
    target: Target
    profile: str
    log: Log
    dry_run: bool
    domain: str = ""
    with_firewall: bool = False
    with_redis: bool = True
    with_minio: bool = True
    secrets_to_hide: list[str] = field(default_factory=list)

    # -- running commands ----------------------------------------------------
    def _redact(self, text: str) -> str:
        for secret in self.secrets_to_hide:
            if secret:
                text = text.replace(secret, "********")
        return text

    def run(
        self,
        argv: list[str],
        *,
        sudo: bool = False,
        as_user: str | None = None,
        input_text: str | None = None,
        check: bool = True,
        quiet: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Run one command that CHANGES something. In `plan` mode it is only
        printed. `argv` is a list, never a shell string, so nothing typed by
        a user can be interpreted as extra commands.
        """
        full = list(argv)
        if as_user:
            full = ["sudo", "-u", as_user, "--"] + full
        elif sudo:
            full = ["sudo", "--"] + full
        if not quiet:
            self.log.cmd(self._redact(shlex.join(full)))
        if self.dry_run:
            return subprocess.CompletedProcess(full, 0, "", "")
        proc = subprocess.run(
            full, input=input_text, text=True, capture_output=True,
            env={**os.environ, **(env or {})},
        )
        if check and proc.returncode != 0:
            tail = self._redact((proc.stderr or proc.stdout or "").strip())[-1500:]
            raise InstallError(f"command failed ({proc.returncode}): {self._redact(shlex.join(full))}\n{tail}")
        return proc

    def probe(
        self, argv: list[str], *, sudo: bool = False, as_user: str | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Run one READ-ONLY command, also in `plan` mode. With sudo it uses
        `sudo -n` (never prompts); if that is refused the probe just reports
        failure, which a check treats as "not done yet".
        """
        full = list(argv)
        if as_user:
            full = ["sudo", "-n", "-u", as_user, "--"] + full
        elif sudo:
            full = ["sudo", "-n", "--"] + full
        try:
            return subprocess.run(full, input=input_text, text=True, capture_output=True)
        except FileNotFoundError:
            return subprocess.CompletedProcess(full, 127, "", "not found")

    # -- small building blocks ----------------------------------------------
    def have(self, command: str) -> bool:
        return shutil.which(command) is not None

    def pkg_installed(self, name: str) -> bool:
        p = self.probe(["dpkg-query", "-W", "-f=${Status}", name])
        return p.returncode == 0 and "install ok installed" in p.stdout

    def apt_install(self, packages: list[str]) -> None:
        missing = [p for p in packages if not self.pkg_installed(p)]
        if not missing:
            return
        self.run(["apt-get", "install", "-y", "--no-install-recommends", *missing],
                 sudo=True, env={"DEBIAN_FRONTEND": "noninteractive"})

    def sudo_read(self, path: Path) -> str | None:
        p = self.probe(["cat", str(path)], sudo=True)
        return p.stdout if p.returncode == 0 else None

    def sudo_exists(self, path: Path) -> bool:
        return self.probe(["test", "-e", str(path)], sudo=True).returncode == 0

    def write_file(self, path: Path, content: str, *, mode: str, owner: str = "root", group: str = "root") -> bool:
        """
        Put `content` at `path` with the given owner and permissions.
        Returns True if the file changed. An existing, different file is
        first copied to `<path>.bak-<timestamp>`.
        """
        current = self.sudo_read(path)
        if current == content:
            self.run(["chown", f"{owner}:{group}", str(path)], sudo=True, quiet=True)
            self.run(["chmod", mode, str(path)], sudo=True, quiet=True)
            return False
        if current is not None:
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            self.run(["cp", "-p", str(path), f"{path}.bak-{stamp}"], sudo=True)
        # `install` creates the file with its final owner and mode in one go,
        # so a secret is never readable by others, even for a moment.
        self.run(["install", "-o", owner, "-g", group, "-m", mode, "/dev/stdin", str(path)],
                 sudo=True, input_text=content)
        return True

    def service_active(self, unit: str) -> bool:
        return self.probe(["systemctl", "is-active", "--quiet", unit]).returncode == 0

    def service_enabled(self, unit: str) -> bool:
        return self.probe(["systemctl", "is-enabled", "--quiet", unit]).returncode == 0

    # -- the secrets file ----------------------------------------------------
    def read_env(self) -> dict[str, str]:
        text = self.sudo_read(ENV_FILE)
        values: dict[str, str] = {}
        if text:
            for line in text.splitlines():
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip()
        return values

    def psql(self, sql: str, *, db: str = "postgres", probe: bool = False) -> subprocess.CompletedProcess:
        """Run SQL as the database superuser. The SQL goes in on stdin, so a
        password inside it never appears in the process list."""
        argv = ["psql", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-d", db]
        if probe:
            return self.probe(argv, as_user="postgres", input_text=sql)
        return self.run(argv, as_user="postgres", input_text=sql, quiet=True)


# ----------------------------------------------------------------------------
# Steps
# ----------------------------------------------------------------------------
@dataclass
class Step:
    id: str
    title: str
    why: str                               # one plain sentence, shown in `plan`
    check: Callable[[Ctx], bool]           # True = already done
    apply: Callable[[Ctx], None]
    enabled: Callable[[Ctx], bool] = lambda ctx: True


# ---- 1. preflight ----------------------------------------------------------
def preflight_check(ctx: Ctx) -> bool:
    """Not a "done / not done" step: it either passes or stops the run."""
    m, t = describe_machine(), ctx.target
    problems = []
    if m["system"] != "Linux":
        problems.append(f"this is {m['system']}, not Linux")
    if (m["os_id"], m["os_version"], m["arch"]) != (t.os_id, t.os_version, t.arch):
        problems.append(
            f"target is {t.id} but this machine is "
            f"{m['os_id']}-{m['os_version']}-{m['arch']}"
        )
    if os.geteuid() == 0:
        problems.append("running as root — run as a normal user that can use sudo")
    if float(m["disk_free_gb"]) < 5:
        problems.append(f"only {m['disk_free_gb']} GB free on / (need 5)")
    if float(m["memory_gb"]) < 1.5:
        problems.append(f"only {m['memory_gb']} GB of memory (need 2)")
    if ctx.profile == "production" and not ctx.domain:
        problems.append("the production profile needs --domain (the console requires HTTPS)")
    if ctx.domain and not re.fullmatch(r"[A-Za-z0-9.-]+", ctx.domain):
        problems.append("--domain may contain only letters, digits, dots and dashes")
    if problems:
        raise InstallError("preflight failed:\n    - " + "\n    - ".join(problems))
    return True


# ---- 2. base packages ------------------------------------------------------
BASE_PACKAGES = [
    "ca-certificates", "curl", "gnupg", "rsync", "openssl",
    "build-essential", "libpq-dev",          # only used if a wheel is missing
    "software-properties-common",
]


def base_check(ctx: Ctx) -> bool:
    return all(ctx.pkg_installed(p) for p in BASE_PACKAGES)


def base_apply(ctx: Ctx) -> None:
    ctx.run(["apt-get", "update"], sudo=True)
    ctx.apt_install(BASE_PACKAGES)


# ---- 3. python --------------------------------------------------------------
def python_packages(ctx: Ctx) -> list[str]:
    py = ctx.target.python
    return [py, f"{py}-venv", f"{py}-dev"]


def python_check(ctx: Ctx) -> bool:
    return all(ctx.pkg_installed(p) for p in python_packages(ctx))


def python_apply(ctx: Ctx) -> None:
    if ctx.target.python_ppa:
        # Ubuntu 22.04 ships Python 3.10; the app needs 3.11+. The PPA is a
        # third-party source: it is added only on targets that declare it.
        ctx.run(["add-apt-repository", "-y", ctx.target.python_ppa], sudo=True)
        ctx.run(["apt-get", "update"], sudo=True)
    ctx.apt_install(python_packages(ctx))


# ---- 4. postgres ------------------------------------------------------------
PG_PACKAGES = [f"postgresql-{PG_VERSION}", f"postgresql-{PG_VERSION}-postgis-3"]


def postgres_check(ctx: Ctx) -> bool:
    return all(ctx.pkg_installed(p) for p in PG_PACKAGES) and ctx.service_active("postgresql")


def postgres_apply(ctx: Ctx) -> None:
    if ctx.target.pg_source == "pgdg" and not ctx.sudo_exists(Path("/etc/apt/sources.list.d/pgdg.list")):
        key = download(ctx, PGDG_KEY_URL)
        verify_gpg_fingerprint(ctx, key, PGDG_KEY_FINGERPRINT)
        ctx.run(["install", "-d", "-m", "0755", str(PGDG_KEYRING.parent)], sudo=True)
        ctx.write_file(PGDG_KEYRING, key, mode="0644")
        line = (f"deb [signed-by={PGDG_KEYRING}] https://apt.postgresql.org/pub/repos/apt "
                f"{ctx.target.codename}-pgdg main\n")
        ctx.write_file(Path("/etc/apt/sources.list.d/pgdg.list"), line, mode="0644")
        ctx.run(["apt-get", "update"], sudo=True)
    ctx.apt_install(PG_PACKAGES)
    ctx.run(["systemctl", "enable", "--now", "postgresql"], sudo=True)


# ---- 5. redis ---------------------------------------------------------------
def redis_check(ctx: Ctx) -> bool:
    return ctx.pkg_installed("redis-server") and ctx.service_active("redis-server")


def redis_apply(ctx: Ctx) -> None:
    ctx.apt_install(["redis-server"])
    ctx.run(["systemctl", "enable", "--now", "redis-server"], sudo=True)


# ---- 6. service user and directories ---------------------------------------
def account_check(ctx: Ctx) -> bool:
    if ctx.probe(["id", "-u", SERVICE_USER]).returncode != 0:
        return False
    return all(ctx.sudo_exists(p) for p in (APP_DIR.parent, ETC_DIR, KEYS_DIR, DATA_DIR))


def account_apply(ctx: Ctx) -> None:
    if ctx.probe(["id", "-u", SERVICE_USER]).returncode != 0:
        # A system account: no password, no login shell, no home directory.
        ctx.run(["useradd", "--system", "--user-group", "--no-create-home",
                 "--shell", "/usr/sbin/nologin", SERVICE_USER], sudo=True)
    ctx.run(["install", "-d", "-o", "root", "-g", "root", "-m", "0755", str(APP_DIR.parent)], sudo=True)
    ctx.run(["install", "-d", "-o", "root", "-g", SERVICE_USER, "-m", "0750", str(ETC_DIR)], sudo=True)
    ctx.run(["install", "-d", "-o", "root", "-g", SERVICE_USER, "-m", "0750", str(KEYS_DIR)], sudo=True)
    ctx.run(["install", "-d", "-o", SERVICE_USER, "-g", SERVICE_USER, "-m", "0750", str(DATA_DIR)], sudo=True)


# ---- 7. secrets and settings -----------------------------------------------
def desired_env(ctx: Ctx, existing: dict[str, str]) -> dict[str, str]:
    """
    Every setting the apps need. A value already in the file is kept — so a
    password is generated exactly once and never changes underneath a running
    database. Only the non-secret, profile-dependent lines are refreshed.
    """
    def keep(key: str, make: Callable[[], str]) -> str:
        return existing.get(key) or make()

    db_password = keep("IDRM_DB_PASSWORD", lambda: secrets.token_urlsafe(32))
    minio_user = keep("S3_ACCESS_KEY", lambda: "idrm-" + secrets.token_hex(6))
    minio_secret = keep("S3_SECRET_KEY", lambda: secrets.token_urlsafe(32))
    production = ctx.profile == "production"
    origin = f"https://{ctx.domain}" if ctx.domain else f"http://127.0.0.1:{API_PORT},http://127.0.0.1:{DASH_PORT}"

    env = {
        "APP_ENV": {"dev": "development", "staging": "staging", "production": "production"}[ctx.profile],
        "LOG_LEVEL": "INFO",
        "ALLOWED_ORIGINS": origin,
        "TRUST_FORWARDED_FOR": "1" if ctx.domain else "0",
        "IDRM_DB_PASSWORD": db_password,
        "DATABASE_URL": f"postgresql+asyncpg://{DB_USER}:{db_password}@127.0.0.1:5432/{DB_NAME}",
        "DATABASE_URL_SYNC": f"postgresql+psycopg2://{DB_USER}:{db_password}@127.0.0.1:5432/{DB_NAME}",
        "REDIS_URL": "redis://127.0.0.1:6379/0" if ctx.with_redis else "",
        "JWT_PRIVATE_KEY_PATH": str(KEYS_DIR / "jwt_private.pem"),
        "JWT_PUBLIC_KEY_PATH": str(KEYS_DIR / "jwt_public.pem"),
        "S3_ENDPOINT": f"http://127.0.0.1:{MINIO_PORT}",
        "S3_BUCKET": "idrm-uploads",
        "S3_ACCESS_KEY": minio_user,
        "S3_SECRET_KEY": minio_secret,
        "S3_REGION": "us-east-1",
        "DASHBOARD_SECRET_KEY": keep("DASHBOARD_SECRET_KEY", lambda: secrets.token_hex(32)),
        "DASHBOARD_SESSION_COOKIE_SECURE": "1" if production else "0",
        "DASHBOARD_ALLOWED_ROLES": "coordinator,admin",
        "ADMIN_INITIAL_PASSWORD": keep("ADMIN_INITIAL_PASSWORD", lambda: secrets.token_urlsafe(18)),
        "AUTO_APPROVAL_ENABLED": existing.get("AUTO_APPROVAL_ENABLED", "1"),
    }
    # Anything an operator added by hand stays.
    for key, value in existing.items():
        env.setdefault(key, value)
    return env


def render_env(env: dict[str, str]) -> str:
    lines = [
        "# IDRM settings and secrets. Written by infra/idrm_infra.py.",
        "# Readable by root and the 'idrm' service user only. Do not commit, do not email.",
        "# Existing values are never regenerated; delete a line to have it made again.",
    ]
    lines += [f"{key}={value}" for key, value in env.items()]
    return "\n".join(lines) + "\n"


def secrets_check(ctx: Ctx) -> bool:
    existing = ctx.read_env()
    if not existing:
        return False
    ctx.secrets_to_hide += [existing.get(k, "") for k in
                            ("IDRM_DB_PASSWORD", "S3_SECRET_KEY", "DASHBOARD_SECRET_KEY", "ADMIN_INITIAL_PASSWORD")]
    return render_env(desired_env(ctx, existing)) == ctx.sudo_read(ENV_FILE)


def secrets_apply(ctx: Ctx) -> None:
    env = desired_env(ctx, ctx.read_env())
    ctx.secrets_to_hide += [env["IDRM_DB_PASSWORD"], env["S3_SECRET_KEY"],
                            env["DASHBOARD_SECRET_KEY"], env["ADMIN_INITIAL_PASSWORD"]]
    ctx.write_file(ENV_FILE, render_env(env), mode="0640", owner="root", group=SERVICE_USER)


# ---- 8. database ------------------------------------------------------------
def database_check(ctx: Ctx) -> bool:
    role = ctx.psql(f"SELECT 1 FROM pg_roles WHERE rolname='{DB_USER}'", probe=True)
    db = ctx.psql(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'", probe=True)
    if role.stdout.strip() != "1" or db.stdout.strip() != "1":
        return False
    ext = ctx.psql("SELECT count(*) FROM pg_extension WHERE extname IN "
                   "('postgis','pgcrypto','pg_trgm','unaccent')", db=DB_NAME, probe=True)
    return ext.stdout.strip() == "4"


def database_apply(ctx: Ctx) -> None:
    password = ctx.read_env().get("IDRM_DB_PASSWORD", "")
    if not password and not ctx.dry_run:
        raise InstallError("no database password in the secrets file — run the 'secrets' step first")
    # The role is NOT a superuser and does not own the extensions: those are
    # created here by the postgres superuser, once.
    role_exists = ctx.psql(f"SELECT 1 FROM pg_roles WHERE rolname='{DB_USER}'", probe=True).stdout.strip() == "1"
    if not role_exists:
        ctx.log.cmd(f"psql: CREATE ROLE {DB_USER} LOGIN PASSWORD '********'")
        ctx.psql(f"CREATE ROLE {DB_USER} LOGIN PASSWORD '{password}';")
    db_exists = ctx.psql(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'", probe=True).stdout.strip() == "1"
    if not db_exists:
        ctx.log.cmd(f"psql: CREATE DATABASE {DB_NAME} OWNER {DB_USER}")
        ctx.psql(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER} ENCODING 'UTF8';")
    ctx.log.cmd("psql: CREATE EXTENSION IF NOT EXISTS postgis, pgcrypto, pg_trgm, unaccent")
    ctx.psql("CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pgcrypto; "
             "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;", db=DB_NAME)


# ---- 9. MinIO ---------------------------------------------------------------
MINIO_BIN = Path("/usr/local/bin/minio")
MINIO_UNIT = Path("/etc/systemd/system/idrm-minio.service")
MINIO_ENV = ETC_DIR / "minio.env"


def minio_unit() -> str:
    return f"""[Unit]
Description=MinIO object storage for IDRM uploads
After=network-online.target
Wants=network-online.target

[Service]
User={SERVICE_USER}
Group={SERVICE_USER}
EnvironmentFile={MINIO_ENV}
ExecStart={MINIO_BIN} server {MINIO_DATA} --address 127.0.0.1:{MINIO_PORT} --console-address 127.0.0.1:9001
Restart=on-failure
RestartSec=5
LimitNOFILE=65536
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={MINIO_DATA}

[Install]
WantedBy=multi-user.target
"""


def minio_check(ctx: Ctx) -> bool:
    return (ctx.sudo_exists(MINIO_BIN) and ctx.sudo_read(MINIO_UNIT) == minio_unit()
            and ctx.service_active("idrm-minio"))


def minio_apply(ctx: Ctx) -> None:
    if not ctx.sudo_exists(MINIO_BIN):
        binary = download(ctx, ctx.target.minio_url, binary=True)
        expected = download(ctx, ctx.target.minio_url + ".sha256sum").split()[0]
        actual = hashlib.sha256(binary).hexdigest() if not ctx.dry_run else expected
        if actual != expected:
            raise InstallError(f"MinIO download does not match its published SHA-256 "
                               f"(expected {expected}, got {actual}) — not installed")
        if not ctx.dry_run:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(binary)
            ctx.run(["install", "-o", "root", "-g", "root", "-m", "0755", tmp.name, str(MINIO_BIN)], sudo=True)
            os.unlink(tmp.name)
        else:
            ctx.log.cmd(f"install -m 0755 <downloaded minio> {MINIO_BIN}")
    env = ctx.read_env()
    ctx.run(["install", "-d", "-o", SERVICE_USER, "-g", SERVICE_USER, "-m", "0750", str(MINIO_DATA)], sudo=True)
    ctx.write_file(MINIO_ENV,
                   f"MINIO_ROOT_USER={env.get('S3_ACCESS_KEY', '')}\nMINIO_ROOT_PASSWORD={env.get('S3_SECRET_KEY', '')}\n",
                   mode="0640", owner="root", group=SERVICE_USER)
    changed = ctx.write_file(MINIO_UNIT, minio_unit(), mode="0644")
    if changed:
        ctx.run(["systemctl", "daemon-reload"], sudo=True)
    ctx.run(["systemctl", "enable", "--now", "idrm-minio"], sudo=True)


# ---- 10. application code and virtualenv -----------------------------------
RSYNC_EXCLUDES = [".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
                  ".env", ".env.*", "keys", "*.pem", "backups", "logs", "node_modules"]


def tree_digest(root: Path) -> str:
    """One hash for the whole source tree, to tell "same code" from "new code"."""
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if any(part in (".git", ".venv", "venv", "__pycache__", "keys", "backups", "logs",
                        ".pytest_cache", ".ruff_cache", "node_modules") for part in path.parts):
            continue
        if path.is_file() and not rel.startswith(".env") and not rel.endswith(".pem"):
            h.update(rel.encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def code_check(ctx: Ctx) -> bool:
    marker = ctx.sudo_read(APP_DIR.parent / "DEPLOYED_DIGEST")
    return (marker is not None and marker.strip() == tree_digest(REPO_ROOT)
            and ctx.sudo_exists(VENV_DIR / "bin" / "gunicorn"))


def code_apply(ctx: Ctx) -> None:
    ctx.run(["install", "-d", "-o", "root", "-g", "root", "-m", "0755", str(APP_DIR)], sudo=True)
    excludes = [arg for pattern in RSYNC_EXCLUDES for arg in ("--exclude", pattern)]
    # The code is owned by root and only READABLE by the service user: a bug
    # in the app cannot rewrite the app.
    ctx.run(["rsync", "-a", "--delete", "--chown=root:root", "--chmod=D755,F644", *excludes,
             f"{REPO_ROOT}/", f"{APP_DIR}/"], sudo=True)
    if not ctx.sudo_exists(VENV_DIR / "bin" / "python"):
        ctx.run([ctx.target.python, "-m", "venv", str(VENV_DIR)], sudo=True)
    pip = str(VENV_DIR / "bin" / "pip")
    ctx.run([pip, "install", "--quiet", "--upgrade", "pip"], sudo=True)
    ctx.run([pip, "install", "--quiet", "-r", str(APP_DIR / "requirements.txt")], sudo=True)
    ctx.write_file(APP_DIR.parent / "DEPLOYED_DIGEST", tree_digest(REPO_ROOT) + "\n", mode="0644")


# ---- 11. JWT keys -----------------------------------------------------------
def keys_check(ctx: Ctx) -> bool:
    return ctx.sudo_exists(KEYS_DIR / "jwt_private.pem") and ctx.sudo_exists(KEYS_DIR / "jwt_public.pem")


def keys_apply(ctx: Ctx) -> None:
    private, public = KEYS_DIR / "jwt_private.pem", KEYS_DIR / "jwt_public.pem"
    # Existing keys are never replaced: that would sign every user out.
    if not ctx.sudo_exists(private):
        ctx.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                 "-out", str(private)], sudo=True)
    ctx.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], sudo=True)
    for path, mode in ((private, "0640"), (public, "0644")):
        ctx.run(["chown", f"root:{SERVICE_USER}", str(path)], sudo=True, quiet=True)
        ctx.run(["chmod", mode, str(path)], sudo=True, quiet=True)


# ---- 12. schema and reference data -----------------------------------------
def app_shell(command: str) -> list[str]:
    """A command run as the service user, with the settings file loaded."""
    script = f"set -a; . {shlex.quote(str(ENV_FILE))}; set +a; cd {shlex.quote(str(APP_DIR))}; {command}"
    return ["bash", "-c", script]


def schema_check(ctx: Ctx) -> bool:
    p = ctx.probe(app_shell(f"{VENV_DIR}/bin/alembic current 2>/dev/null"), as_user=SERVICE_USER)
    if p.returncode != 0 or "(head)" not in p.stdout:
        return False
    regions = ctx.psql("SELECT count(*) FROM regions", db=DB_NAME, probe=True)
    return regions.returncode == 0 and regions.stdout.strip() not in ("", "0")


def schema_apply(ctx: Ctx) -> None:
    ctx.run(app_shell(f"{VENV_DIR}/bin/alembic upgrade head"), as_user=SERVICE_USER)
    # Demo users (with a published password) only on a development machine.
    seed = "python -m scripts.seed" if ctx.profile == "dev" else "python -m scripts.seed --reference-only"
    ctx.run(app_shell(f"{VENV_DIR}/bin/{seed}"), as_user=SERVICE_USER)


# ---- 13. services -----------------------------------------------------------
def app_unit(name: str, description: str, exec_start: str) -> str:
    return f"""[Unit]
Description={description}
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
User={SERVICE_USER}
Group={SERVICE_USER}
WorkingDirectory={APP_DIR}
EnvironmentFile={ENV_FILE}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
# --- hardening: the service can read its code and settings, and nothing else
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
"""


def unit_texts() -> dict[str, str]:
    gunicorn = VENV_DIR / "bin" / "gunicorn"
    return {
        "idrm-api": app_unit(
            "idrm-api", "IDRM public API (FastAPI)",
            f"{gunicorn} -w 2 -k uvicorn.workers.UvicornWorker --access-logfile - --error-logfile - "
            f"-b 127.0.0.1:{API_PORT} app.main:app"),
        "idrm-dashboard": app_unit(
            "idrm-dashboard", "IDRM staff console (Flask)",
            f"{gunicorn} -w 2 --access-logfile - --error-logfile - "
            f"-b 127.0.0.1:{DASH_PORT} dashboard:create_dashboard()"),
    }


def services_check(ctx: Ctx) -> bool:
    for name, text in unit_texts().items():
        if ctx.sudo_read(Path(f"/etc/systemd/system/{name}.service")) != text:
            return False
        if not (ctx.service_enabled(name) and ctx.service_active(name)):
            return False
    return True


def services_apply(ctx: Ctx) -> None:
    changed = False
    for name, text in unit_texts().items():
        changed |= ctx.write_file(Path(f"/etc/systemd/system/{name}.service"), text, mode="0644")
    if changed:
        ctx.run(["systemctl", "daemon-reload"], sudo=True)
    for name in unit_texts():
        ctx.run(["systemctl", "enable", name], sudo=True)
        ctx.run(["systemctl", "restart", name], sudo=True)


# ---- 14. nginx (only with --domain) ----------------------------------------
def nginx_site(ctx: Ctx) -> str:
    return f"""# Written by infra/idrm_infra.py — reverse proxy for IDRM.
# HTTPS is added by certbot (see docs/infra/INFRASTRUCTURE-MASTER-PLAN.md, section 11).
server {{
    listen 80;
    listen [::]:80;
    server_name {ctx.domain};

    client_max_body_size 12m;

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    # Overwrite (not append) so a client cannot fake its address.
    proxy_set_header X-Forwarded-For   $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;

    location /dashboard {{ proxy_pass http://127.0.0.1:{DASH_PORT}; }}
    location /          {{ proxy_pass http://127.0.0.1:{API_PORT}; }}
}}
"""


NGINX_SITE = Path("/etc/nginx/sites-available/idrm")
NGINX_LINK = Path("/etc/nginx/sites-enabled/idrm")


def nginx_check(ctx: Ctx) -> bool:
    return (ctx.pkg_installed("nginx") and ctx.sudo_read(NGINX_SITE) == nginx_site(ctx)
            and ctx.sudo_exists(NGINX_LINK) and ctx.service_active("nginx"))


def nginx_apply(ctx: Ctx) -> None:
    ctx.apt_install(["nginx"])
    ctx.write_file(NGINX_SITE, nginx_site(ctx), mode="0644")
    ctx.run(["ln", "-sfn", str(NGINX_SITE), str(NGINX_LINK)], sudo=True)
    ctx.run(["nginx", "-t"], sudo=True)                 # refuse to reload a broken config
    ctx.run(["systemctl", "enable", "--now", "nginx"], sudo=True)
    ctx.run(["systemctl", "reload", "nginx"], sudo=True)


# ---- 15. firewall (only with --with-firewall) ------------------------------
def ssh_ports() -> list[str]:
    """
    Ports SSH must stay reachable on: the standard one, plus the one THIS
    session came in on (SSH_CONNECTION = "client-ip client-port server-ip
    server-port"), in case the server uses a non-standard port.
    """
    ports = ["22"]
    parts = os.environ.get("SSH_CONNECTION", "").split()
    if len(parts) == 4 and parts[3].isdigit() and parts[3] not in ports:
        ports.append(parts[3])
    return ports


def firewall_check(ctx: Ctx) -> bool:
    p = ctx.probe(["ufw", "status"], sudo=True)
    return (p.returncode == 0 and "Status: active" in p.stdout
            and all(f"{port}/tcp" in p.stdout for port in ssh_ports()))


def firewall_apply(ctx: Ctx) -> None:
    ctx.apt_install(["ufw"])
    # SSH is allowed BEFORE the firewall is switched on, so a remote session
    # is not cut off.
    for port in ssh_ports():
        ctx.run(["ufw", "allow", f"{port}/tcp"], sudo=True)
    if ctx.domain:
        ctx.run(["ufw", "allow", "80/tcp"], sudo=True)
        ctx.run(["ufw", "allow", "443/tcp"], sudo=True)
    ctx.run(["ufw", "default", "deny", "incoming"], sudo=True)
    ctx.run(["ufw", "default", "allow", "outgoing"], sudo=True)
    ctx.run(["ufw", "--force", "enable"], sudo=True)


def build_steps() -> list[Step]:
    return [
        Step("preflight", "Check this machine",
             "Stops early if the machine is not the one the target script is for, or is too small.",
             lambda ctx: False, lambda ctx: None),
        Step("base", "Base packages",
             "Tools the later steps use: certificates, curl, rsync, a compiler as a fallback.",
             base_check, base_apply),
        Step("python", "Python for the application",
             "The apps need Python 3.11 or newer, with the venv module.",
             python_check, python_apply),
        Step("postgres", f"PostgreSQL {PG_VERSION} + PostGIS",
             "The database. PostGIS adds the map functions (regions, nearby search).",
             postgres_check, postgres_apply),
        Step("redis", "Redis",
             "Optional cache and counters. The platform also runs without it.",
             redis_check, redis_apply, enabled=lambda ctx: ctx.with_redis),
        Step("account", "Service user and directories",
             "The apps run as an unprivileged 'idrm' user, not as you and not as root.",
             account_check, account_apply),
        Step("secrets", "Settings and secrets file",
             "Generates the passwords once and stores them where only root and 'idrm' can read.",
             secrets_check, secrets_apply),
        Step("database", "Database role, database and extensions",
             "Creates the app's own database login (not a superuser) and switches on PostGIS.",
             database_check, database_apply),
        Step("minio", "MinIO object storage",
             "Stores uploaded photos and documents. Needed only for file uploads.",
             minio_check, minio_apply, enabled=lambda ctx: ctx.with_minio),
        Step("code", "Application code and Python packages",
             "Copies this repository to /opt/idrm/app and installs its requirements in a virtualenv.",
             code_check, code_apply),
        Step("keys", "JWT signing keys",
             "The key pair that signs login tokens. Made once; replacing it signs everyone out.",
             keys_check, keys_apply),
        Step("schema", "Database schema and reference data",
             "Runs the migrations and loads the regions (demo users only with --profile dev).",
             schema_check, schema_apply),
        Step("services", "systemd services",
             "Starts the API and the console now and at every boot, restarting them if they crash.",
             services_check, services_apply),
        Step("nginx", "nginx reverse proxy",
             "The single public entry point; HTTPS is added on top with certbot.",
             nginx_check, nginx_apply, enabled=lambda ctx: bool(ctx.domain)),
        Step("firewall", "Firewall",
             "Allows SSH (and web traffic) in and nothing else.",
             firewall_check, firewall_apply, enabled=lambda ctx: ctx.with_firewall),
    ]


# ----------------------------------------------------------------------------
# Downloads
# ----------------------------------------------------------------------------
def download(ctx: Ctx, url: str, *, binary: bool = False):
    """Fetch over HTTPS only. In `plan` mode nothing is fetched."""
    if not url.startswith("https://"):
        raise InstallError(f"refusing to download over an insecure URL: {url}")
    ctx.log.cmd(f"download {url}")
    if ctx.dry_run:
        return b"" if binary else "0" * 64 + "  plan-mode"
    request = urllib.request.Request(url, headers={"User-Agent": "idrm-infra"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    return data if binary else data.decode("utf-8")


def verify_gpg_fingerprint(ctx: Ctx, key_text: str, expected: str) -> None:
    if ctx.dry_run:
        ctx.log.cmd(f"gpg --show-keys  (must be {expected})")
        return
    p = subprocess.run(["gpg", "--show-keys", "--with-colons"], input=key_text, text=True, capture_output=True)
    prints = [line.split(":")[9] for line in p.stdout.splitlines() if line.startswith("fpr:")]
    if expected not in prints:
        raise InstallError(f"signing key fingerprint mismatch: expected {expected}, got {prints} — not trusted")


# ----------------------------------------------------------------------------
# Verify: a health report that changes nothing
# ----------------------------------------------------------------------------
def verify(ctx: Ctx) -> int:
    log, failures = ctx.log, 0

    def result(ok: bool, label: str, detail: str = "") -> None:
        nonlocal failures
        if ok:
            log.ok(label)
        else:
            failures += 1
            log.err(label + (f" — {detail}" if detail else ""))

    log.head("Services")
    units = ["postgresql", "idrm-api", "idrm-dashboard"]
    units += ["redis-server"] if ctx.with_redis else []
    units += ["idrm-minio"] if ctx.with_minio else []
    units += ["nginx"] if ctx.domain else []
    for unit in units:
        result(ctx.service_active(unit), f"{unit} is running")

    log.head("Application")
    api = ctx.probe(["curl", "-fsS", "-o", "/dev/null", "-w", "%{http_code}",
                     f"http://127.0.0.1:{API_PORT}/api/v1/health"])
    result(api.stdout.strip() == "200", "API health is 200", f"got {api.stdout.strip() or 'no answer'}")
    dash = ctx.probe(["curl", "-fsS", "-o", "/dev/null", "-w", "%{http_code}",
                      f"http://127.0.0.1:{DASH_PORT}/dashboard/auth/login"])
    result(dash.stdout.strip() == "200", "Console login page is 200", f"got {dash.stdout.strip() or 'no answer'}")

    log.head("Exposure — nothing but the proxy should listen on a public address")
    listening = ctx.probe(["ss", "-ltnH"]).stdout
    for port, name in ((5432, "PostgreSQL"), (6379, "Redis"), (MINIO_PORT, "MinIO"),
                       (API_PORT, "API"), (DASH_PORT, "Console")):
        public = [line for line in listening.splitlines()
                  if re.search(rf"(0\.0\.0\.0|\*|\[::\]):{port}\s", line)]
        result(not public, f"{name} (port {port}) is not reachable from other machines")

    log.head("Secrets")
    stat = ctx.probe(["stat", "-c", "%a %U %G", str(ENV_FILE)], sudo=True).stdout.strip()
    result(stat == f"640 root {SERVICE_USER}", f"{ENV_FILE} is 640 root:{SERVICE_USER}", f"is '{stat or 'unreadable'}'")
    stat = ctx.probe(["stat", "-c", "%a %U %G", str(KEYS_DIR / "jwt_private.pem")], sudo=True).stdout.strip()
    result(stat == f"640 root {SERVICE_USER}", "JWT private key is 640 root:idrm", f"is '{stat or 'unreadable'}'")

    print()
    if failures:
        log.err(f"{failures} check(s) failed")
        return 1
    log.ok("all checks passed")
    return 0


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
def select_steps(ctx: Ctx, args) -> list[Step]:
    steps = [s for s in build_steps() if s.enabled(ctx)]
    ids = [s.id for s in steps]
    for wanted in (args.only or []) + ([args.start_from] if args.start_from else []):
        if wanted not in ids:
            raise InstallError(f"unknown or disabled step '{wanted}'. Steps: {', '.join(ids)}")
    if args.only:
        # preflight always runs: it is the safety check.
        steps = [s for s in steps if s.id in args.only or s.id == "preflight"]
    if args.start_from:
        index = ids.index(args.start_from)
        steps = [s for s in steps if s.id == "preflight" or ids.index(s.id) >= index]
    return steps


def cmd_detect(_args) -> int:
    m = describe_machine()
    print("This machine:")
    for key, value in m.items():
        print(f"  {key:14} {value}")
    print(f"\nTarget id: {m['os_id']}-{m['os_version']}-{m['arch']}")
    return 0


def cmd_plan_or_apply(args, *, apply: bool) -> int:
    log = Log()
    ctx = Ctx(
        target=Target.from_env(), profile=args.profile, log=log, dry_run=not apply,
        domain=args.domain or "", with_firewall=args.with_firewall,
        with_redis=not args.without_redis, with_minio=not args.without_minio,
    )
    log.head(f"IDRM infrastructure — {'APPLY' if apply else 'PLAN (nothing will be changed)'}")
    log.info(f"target  {ctx.target.id}")
    log.info(f"profile {ctx.profile}" + (f"   domain {ctx.domain}" if ctx.domain else ""))
    if log.path:
        log.info(f"log     {log.path}")

    preflight_check(ctx)
    steps = select_steps(ctx, args)

    pending = []
    for step in steps:
        if step.id == "preflight":
            continue
        done = step.check(ctx)
        (log.ok if done else log.todo)(f"{step.id:10} {step.title}" + ("" if done else f" — {step.why}"))
        if not done:
            pending.append(step)

    if not pending:
        log.head("Nothing to do — this machine already matches the plan.")
        return 0
    if not apply:
        log.head(f"{len(pending)} step(s) would run. To carry them out:  ... apply")
        for step in pending:
            log.head(f"[plan] {step.id}: {step.title}")
            try:
                step.apply(ctx)
            except InstallError as exc:
                log.warn(f"cannot be planned in detail yet: {exc}")
        return 0

    if not args.yes:
        answer = input(f"\nRun {len(pending)} step(s) on this machine? Type 'yes' to continue: ")
        if answer.strip().lower() != "yes":
            log.warn("stopped — nothing was changed")
            return 1
    subprocess.run(["sudo", "-v"], check=True)        # ask for the sudo password once, up front

    for step in pending:
        log.head(f"{step.id}: {step.title}")
        step.apply(ctx)
        if not step.check(ctx):
            raise InstallError(f"step '{step.id}' ran but its check still fails — stopping here")
        log.ok(f"{step.id} done")

    # New code, settings or keys only take effect when the apps restart. If
    # the services step itself did not run (the units were already right),
    # restart them here.
    ran = {s.id for s in pending}
    if ran & {"secrets", "code", "keys", "schema"} and "services" not in ran:
        for name in unit_texts():
            if ctx.sudo_exists(Path(f"/etc/systemd/system/{name}.service")):
                log.head(f"restart {name} (picks up the change)")
                ctx.run(["systemctl", "restart", name], sudo=True)

    log.head("Applied. Health check:")
    code = verify(ctx)
    if any(s.id == "secrets" for s in pending):
        log.head("First-time secrets")
        log.info(f"The admin password and all other secrets are in {ENV_FILE}")
        log.info(f"Read the admin password with:  sudo grep ADMIN_INITIAL_PASSWORD {ENV_FILE}")
    return code


def cmd_verify(args) -> int:
    ctx = Ctx(target=Target.from_env(), profile=args.profile, log=Log(), dry_run=True,
              domain=args.domain or "", with_firewall=args.with_firewall,
              with_redis=not args.without_redis, with_minio=not args.without_minio)
    return verify(ctx)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IDRM infrastructure installer", epilog=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("detect", help="describe this machine")
    sub.add_parser("steps", help="list the steps")
    for name, text in (("plan", "show what would be done; changes nothing"),
                       ("apply", "carry out the plan"),
                       ("verify", "health report; changes nothing")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--profile", choices=PROFILES, default="staging",
                       help="dev: demo data. staging: real settings, no HTTPS. production: needs --domain")
        p.add_argument("--domain", help="public host name; adds the nginx step")
        p.add_argument("--with-firewall", action="store_true", help="also configure ufw (off by default)")
        p.add_argument("--without-redis", action="store_true")
        p.add_argument("--without-minio", action="store_true")
        p.add_argument("--only", action="append", metavar="STEP", help="run just this step (repeatable)")
        p.add_argument("--from", dest="start_from", metavar="STEP", help="start at this step")
        p.add_argument("--yes", action="store_true", help="do not ask before applying")
    args = parser.parse_args(argv)

    try:
        if args.command == "detect":
            return cmd_detect(args)
        if args.command == "steps":
            for step in build_steps():
                print(f"  {step.id:10} {step.title}\n             {step.why}")
            return 0
        # One run at a time: two installers editing the same files would collide.
        import fcntl                     # Linux only; `detect` works without it

        lock = open(Path(tempfile.gettempdir()) / "idrm-infra.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("another idrm_infra.py run is in progress — try again when it ends", file=sys.stderr)
            return 2
        if args.command == "verify":
            return cmd_verify(args)
        return cmd_plan_or_apply(args, apply=args.command == "apply")
    except InstallError as exc:
        print(_c("31", f"\n✗ {exc}"), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted — completed steps stay done; run again to continue", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
