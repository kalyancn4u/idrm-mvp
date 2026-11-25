# IDRM Infrastructure Master Plan

> **Scope:** building or patching an IDRM server with the installer.  
> **Owner of:** the server layout and the installer steps.  
> **See also:** [../07-operations.md](../07-operations.md) · [../DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md)

Product requirements and functional specification for getting an IDRM server
ready — from an empty Ubuntu machine, or as a small patch to one that is
already running.

| | |
|---|---|
| Status | Draft for review — written 2026-11-15 |
| Applies to | the `idrm-mvp` repository (FastAPI API + Flask console) |
| Implemented by | `infra/install.sh`, `infra/targets/*.sh`, `infra/idrm_infra.py` |
| Tested | `detect`, `plan`, `verify` and the refusal cases on Ubuntu 22.04 amd64 (WSL). **`apply` has never been run.** See [section 14](#14-what-has-and-has-not-been-tested) |

## How to read this

- **In a hurry?** Read sections 1, 4 and 10.
- **New to servers?** Read section 2 (the words) first, then go in order.
- **Reviewing the design?** Sections 5 to 9 are the specification.

---

## 1. The short version

One command decides what this machine needs and shows it to you. A second
command does it.

```bash
bash infra/install.sh            # show the plan; change nothing
bash infra/install.sh apply      # carry it out (asks first)
bash infra/install.sh verify     # health report
```

Three ideas hold the whole design together:

1. **Every step can tell whether it is already done.** So running the
   installer again is safe, and it only does what is missing. This is what
   makes "from scratch" and "small patch" the same command.
2. **Nothing changes until you say `apply`.** The default is to show the plan.
3. **Differences between machines live in small files**, one per operating
   system and processor type. The logic is written once.

---

## 2. Words you need

| Word | Plain meaning |
|---|---|
| **Infrastructure** | Everything the application needs around it: the database, storage, the user it runs as, the files that hold its settings, the service that keeps it running. |
| **Idempotent** | Doing it twice gives the same result as doing it once. A light switch labelled "on" is idempotent; a switch labelled "toggle" is not. |
| **Target** | One operating system + version + processor type, for example "Ubuntu 24.04 on amd64". |
| **amd64 / arm64** | Two families of processor. Intel and AMD chips are amd64 (also written x86_64). Graviton, Ampere and Raspberry Pi are arm64 (also aarch64). A program built for one does not run on the other. |
| **LTS** | "Long-term support": an Ubuntu release that gets security fixes for years. 22.04 and 24.04 are LTS. |
| **sudo** | Run one command as the administrator (root). |
| **Service user** | A login-less account that exists only to run a program, so that program has as little power as possible. |
| **systemd** | The part of Linux that starts programs at boot and restarts them if they crash. A **unit** is its description of one program. |
| **Secret** | A password or key. Whoever has it can act as the system. |
| **Reverse proxy** | A program (here nginx) that receives traffic from the internet and passes it to the right application behind it. |
| **Profile** | A named purpose for the install: `dev`, `staging` or `production`. |
| **Plan / apply** | Plan = say what would be done. Apply = do it. |

---

## 3. What exists today

The command you asked for, run in Git Bash on this laptop:

```bash
cd ~/Downloads
find idrm-* -iname '*.sh'
```

It finds **116 shell scripts in five folders. Only 66 are different from each
other** — the rest are copies.

| Folder | Scripts | What they are |
|---|---:|---|
| `idrm-artifacts/` | 35 | Two copies of a 17-file setup set under `archive/`, plus one slide builder |
| `idrm-monorepo/` | 43 | The same two copies again, plus doc-link fixers and four stubs (3 to 9 lines) |
| `idrm-scripts-monorepo/` | 33 | One-off scripts that generated or migrated documentation; none install anything |
| `idrm-mvp/` | 3 | `bootstrap.sh`, `run_all.sh`, `smoke.sh` — the current project |
| `idrm-dashboard/` | 2 | An older `bootstrap.sh` and `smoke.sh` |

### The 17-file setup set (exists four times)

| Script | Lines | Purpose |
|---|---:|---|
| `setup-idrm-ubuntu.sh` | 1,047 / 1,099 (two versions) | Sets up a **developer workstation**: PostgreSQL, MinIO, Miniconda, VS Codium, Chrome, DBeaver |
| `install-devops-stack.sh` + three numbered variants | 920 to 1,191 | Installs ~25 groups of tools: Java, Bun, Docker, editors, browsers, Wine, GNOME apps |
| `check-devops-stack.sh` + two variants | ~1,055 | Reports what is installed |
| `update-maintain-system.sh`, `setup-update-system.sh` | 569, 458 | apt / snap upgrades and cleanup |
| `setup-prerequisites.sh`, `setup-development-*.sh`, `setup-staging.sh`, `setup-production.sh` | 27 to 158 | Docker Compose wrappers for an older repository layout |
| `_lib.sh` | 72 | Shared logging and helper functions — the best-written file of the set |
| `services-disable.sh` | 55 | Stops services |

### What is wrong with it, as a way to build a server

| # | Finding | Evidence | Why it matters |
|---|---|---|---|
| 1 | **Passwords are written in the scripts** | `setup-idrm-ubuntu.sh:225` creates the database user with `idrm_secure_password_2024`; line 273 sets `idrm_minio_password_2024`; both are printed at the end | Every machine built this way has the same, publicly visible passwords |
| 2 | **Workstation and server are mixed** | The same script installs PostgreSQL and Google Chrome | A server should carry nothing it does not need; each extra program is something to patch and something to attack |
| 3 | **One processor type only** | `linux-amd64` and `x86_64` are hard-coded in the download URLs | It cannot build an ARM server |
| 4 | **Old way of trusting package sources** | `apt-key add` (lines 173, 464) | `apt-key` is deprecated: a key added this way is trusted for *every* package source, not just the one it belongs to |
| 5 | **Four copies, several "(1) (2) (3)" variants** | 116 files, 66 unique | Nobody can say which one is current; a fix in one copy leaves three others wrong |
| 6 | **No "show me first" mode in the main script** | `setup-idrm-ubuntu.sh` starts changing the system at once | You cannot review what it will do |
| 7 | **Does not match the current code** | It builds a Miniconda environment and a Bun/Node layout; the current project is a plain Python virtualenv with two apps | Following it does not produce a machine that runs `idrm-mvp` |
| 8 | **Nothing runs the application** | No systemd unit, no service user | After it finishes, the apps are not started and would run as the person who typed the command |

What is worth keeping from it: the logging style and the `have` / `confirm` /
`ensure_env` helpers in `_lib.sh`, the three-phase idea in
`install-devops-stack.sh` (add sources, update once, install), and its
`--dry-run` flag. The new installer keeps those ideas.

**Recommended disposal** (not done — these folders are outside this
repository): keep one copy of the 17-file set in an `archive/` folder for
reference and delete the other three; keep `idrm-scripts-monorepo/` only if
the documentation migration it performed might be repeated.

---

## 4. What is being built

### 4.1 Goals

| ID | Goal |
|---|---|
| G1 | One command takes an empty supported Ubuntu server to a running IDRM |
| G2 | The same command, run again, changes nothing |
| G3 | The same command applies a small change (new code, one new step) without redoing the rest |
| G4 | No password is written in the repository, shown on screen, or shared between machines |
| G5 | Nothing but the web entry point is reachable from another machine |
| G6 | The operator sees every privileged command before it runs |
| G7 | A machine the installer was not written for is refused, never guessed at |
| G8 | Supporting a new machine type means adding one small file |

### 4.2 Not goals

Stated so nobody assumes otherwise:

- **A developer workstation.** Editors, browsers and database GUIs are your
  choice. For development use Docker: `make setup` then `make run`
  (see `docs/01-getting-started.md`).
- **More than one server.** Database, storage and both apps go on one machine.
  Splitting them is future work.
- **Getting the HTTPS certificate.** It needs your domain name and an email
  address, and it talks to an outside service, so you run it yourself
  ([section 11](#11-https)).
- **Backups, monitoring, log shipping.** Described in `docs/07-operations.md`;
  not automated here.
- **Other Linux families, macOS, Windows.** Only the targets in section 5.

### 4.3 Who uses it

| Person | Wants | Uses |
|---|---|---|
| **First-time operator** | A working server without learning every tool first | `install.sh`, then `install.sh apply`, reading the plan in between |
| **Maintainer deploying a change** | To ship new code safely | `install.sh apply --only code --only services` |
| **Reviewer or auditor** | To know exactly what will touch the machine | `install.sh plan`, and this document |
| **Someone with new hardware** | To add a machine type | One new file in `infra/targets/` |

---

## 5. Supported machines

A **target** is operating system + version + processor type. Each has its own
script; the differences between them are the whole content of that script.

| Target script | Hardware | Python | PostgreSQL 16 from | Outside package sources |
|---|---|---|---|---|
| `ubuntu-24.04-amd64.sh` | Intel/AMD servers, most cloud VMs | 3.12 (Ubuntu's) | Ubuntu's archive | none |
| `ubuntu-24.04-arm64.sh` | Graviton, Ampere, Raspberry Pi 4/5 | 3.12 (Ubuntu's) | Ubuntu's archive | none |
| `ubuntu-22.04-amd64.sh` | Intel/AMD on the older LTS | 3.11 | apt.postgresql.org | deadsnakes PPA, PostgreSQL project repository |
| `ubuntu-22.04-arm64.sh` | ARM on the older LTS | 3.11 | apt.postgresql.org | deadsnakes PPA, PostgreSQL project repository |

**Prefer Ubuntu 24.04.** It ships everything needed, so you trust only
Ubuntu. On 22.04 two more sources must be trusted, because 22.04 has Python
3.10 (the app needs 3.11+) and PostgreSQL 14 (the app needs 16).

Minimum size: 2 GB memory, 5 GB free disk. The installer refuses less.

### Adding a target

1. Copy the closest file in `infra/targets/`, named `<os>-<version>-<arch>.sh`.
2. Change the nine `IDRM_*` values.
3. Run it with no arguments and read the plan.

If the new machine needs different *steps* (not just different values) —
another Linux family, for instance — that is a change to `idrm_infra.py`, not
a new target file.

---

## 6. What ends up on the server

```
                    internet
                       │
        ┌──────────────▼──────────────┐
        │ nginx :80 / :443            │  only with --domain
        └───────┬──────────────┬──────┘
   /dashboard…  │              │  everything else
        ┌───────▼─────┐  ┌─────▼────────┐
        │ console     │  │ API          │   run as user "idrm"
        │ 127.0.0.1   │  │ 127.0.0.1    │   started by systemd
        │ :5000       │  │ :8000        │
        └───────┬─────┘  └─────┬────────┘
                └──────┬───────┘
     ┌─────────────────┼─────────────────┐
┌────▼──────┐   ┌──────▼─────┐   ┌───────▼─────┐
│PostgreSQL │   │ Redis      │   │ MinIO       │   all on 127.0.0.1
│+ PostGIS  │   │ (optional) │   │ (uploads)   │
│ :5432     │   │ :6379      │   │ :9000       │
└───────────┘   └────────────┘   └─────────────┘
```

| Path | What | Owner : group | Mode |
|---|---|---|---|
| `/opt/idrm/app/` | A copy of this repository | root : root | read-only to the service |
| `/opt/idrm/venv/` | Python packages | root : root | read-only to the service |
| `/etc/idrm/idrm.env` | Settings **and secrets** | root : idrm | 640 |
| `/etc/idrm/keys/jwt_private.pem` | Key that signs login tokens | root : idrm | 640 |
| `/etc/idrm/minio.env` | MinIO credentials | root : idrm | 640 |
| `/var/lib/idrm/minio/` | Uploaded files | idrm : idrm | 750 |
| `/etc/systemd/system/idrm-*.service` | How to run the API, console, MinIO | root : root | 644 |
| `/etc/nginx/sites-available/idrm` | Proxy rules | root : root | 644 |
| `~/.local/state/idrm-infra/` | One log file per installer run | you | — |

The code is owned by root and only *readable* by `idrm`. If the application
is ever tricked into writing files, it cannot rewrite itself.

---

## 7. Functional specification

### 7.1 Files

| File | Role | Size |
|---|---|---|
| `infra/install.sh` | Finds out what this machine is and runs the matching target script. Stops if there is none | ~50 lines |
| `infra/targets/<target>.sh` | Says what is different about one machine, then calls the master script | ~30 lines each |
| `infra/lib/common.sh` | The dozen lines the target scripts share | ~45 lines |
| `infra/idrm_infra.py` | **The master script.** All steps, checks and safety rules. Python standard library only | ~1170 lines |

### 7.2 Commands

| Command | Changes the machine? | Does |
|---|---|---|
| `detect` | no | Prints OS, version, processor type, memory, free disk |
| `steps` | no | Lists the steps with one sentence each |
| `plan` (default) | no | Checks each step; prints what is done, what is missing, and the exact commands `apply` would run |
| `apply` | **yes** | Asks for confirmation, then runs the missing steps in order and finishes with `verify` |
| `verify` | no | Health report: services, the two apps, what is exposed, file permissions. Exit code 1 if anything fails |

### 7.3 Options

| Option | Meaning |
|---|---|
| `--profile dev` | Development machine: loads **demo users with a published password** |
| `--profile staging` (default) | Real settings and generated secrets, no HTTPS. For a first bring-up or an internal test server |
| `--profile production` | Needs `--domain`. Sets `APP_ENV=production`, which makes both apps refuse to start on any development default |
| `--domain NAME` | Adds the nginx step for that host name |
| `--with-firewall` | Adds the firewall step. Off by default because a wrong firewall rule can lock you out |
| `--without-redis`, `--without-minio` | Skip those services |
| `--only STEP` | Run just this step (repeatable). The machine check always runs |
| `--from STEP` | Start at this step |
| `--yes` | Do not ask before applying — for automation |

### 7.4 The steps

Each step has a **check** (read-only: "is this already done?") and an
**apply** (the work). `apply` runs only where the check says no.

| # | Step | Done when | Apply does |
|---|---|---|---|
| 1 | `preflight` | — (pass or stop) | Confirms target matches the machine, not root, enough memory and disk, production has a domain |
| 2 | `base` | Packages installed | `apt-get install` certificates, curl, rsync, openssl, a compiler as fallback |
| 3 | `python` | Interpreter + venv module installed | Installs the target's Python (adds the PPA only on 22.04) |
| 4 | `postgres` | Packages installed, service running | Installs PostgreSQL 16 + PostGIS; on 22.04 first adds the PostgreSQL repository after checking its key fingerprint |
| 5 | `redis` | Installed and running | Installs Redis (listens on 127.0.0.1 by default) |
| 6 | `account` | User and directories exist | Creates the login-less `idrm` user and `/opt/idrm`, `/etc/idrm`, `/var/lib/idrm` |
| 7 | `secrets` | File matches what is wanted | Generates each secret **once**; keeps every value already present |
| 8 | `database` | Role, database and four extensions exist | Creates a non-superuser role, the database, and PostGIS / pgcrypto / pg_trgm / unaccent |
| 9 | `minio` | Binary, unit and service present | Downloads the binary for this processor type, checks its SHA-256, runs it on 127.0.0.1 |
| 10 | `code` | Deployed copy has the same content hash as this checkout | Copies the repository, builds the virtualenv, installs requirements |
| 11 | `keys` | Both key files exist | Generates the JWT key pair. Never replaces an existing one |
| 12 | `schema` | Migrations at head and regions present | `alembic upgrade head`, then reference data (demo data only with `--profile dev`) |
| 13 | `services` | Units match, enabled and running | Writes hardened systemd units, enables and restarts them |
| 14 | `nginx` | *(with `--domain`)* Site matches and nginx runs | Installs nginx, writes the site, tests the config before reloading |
| 15 | `firewall` | *(with `--with-firewall`)* Active and SSH allowed | Allows SSH **first**, then web ports, then enables |

Order matters and is fixed: the secrets file exists before the database role
is created with its password; the code is deployed before migrations run.

### 7.5 Rules the installer must obey

| ID | Rule | How it is met |
|---|---|---|
| FR-1 | A second `apply` with no change in between runs zero steps | Every step has a read-only check |
| FR-2 | `plan` never changes the machine | In plan mode `run()` only prints; checks use `sudo -n`, which never prompts |
| FR-3 | A step that ran must pass its own check, or the run stops | Check is repeated after apply |
| FR-4 | An interrupted run can be resumed | Completed steps stay done; run again |
| FR-5 | The wrong target script is refused | `preflight` compares the target with `/etc/os-release` and the processor type |
| FR-6 | Two runs cannot overlap | A lock file; the second run exits with code 2 |
| FR-7 | Every run leaves a record | One log file per run, with secrets replaced by `********` |

---

## 8. Safety and security measures

| Risk | Measure |
|---|---|
| Changing a machine by surprise | `plan` is the default; `apply` asks you to type `yes` |
| Hidden privileged actions | Run as a normal user; each `sudo` command is printed before it runs |
| Passwords in the repository | None. All are generated on the machine with Python's `secrets` module |
| Passwords on screen or in logs | Replaced by `********` in every printed command and in the log |
| Passwords in the process list | SQL containing the password is sent to `psql` on standard input, not as an argument |
| A secret briefly readable by others | Files are created with their final owner and mode in one operation (`install -m`) |
| Regenerating a password under a running database | A value already in `/etc/idrm/idrm.env` is always kept |
| Losing a config file | Any file about to be replaced is first copied to `<name>.bak-<timestamp>` |
| Everyone signed out by accident | Existing JWT keys are never replaced |
| Database reachable from outside | PostgreSQL, Redis, MinIO and both apps listen on 127.0.0.1; `verify` checks this |
| A compromised app rewriting itself | Code and virtualenv are owned by root; the service user can only read them |
| A compromised app reaching the rest of the system | systemd hardening: `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `PrivateDevices` |
| The app's database login being too powerful | It is not a superuser; extensions are created once by the `postgres` superuser |
| Demo accounts on a real server | Demo seed runs only with `--profile dev`, and the seed itself refuses in production |
| Shipping development defaults | With `--profile production` the apps refuse to start on any of them |
| A tampered download | HTTPS only. PostgreSQL's key must match a fingerprint written in the script; MinIO must match its published SHA-256 |
| `curl … \| bash` | Not used anywhere |
| Trusting a key for everything | Package sources use `signed-by=`, so a key is trusted for its own source only |
| Locking yourself out with the firewall | Opt-in; SSH (port 22 and the port of your current session) is allowed before it is switched on |
| A broken nginx config taking the site down | `nginx -t` must pass before reload |
| Commands built from user input | Commands are lists, never shell strings; `--domain` accepts only letters, digits, dots and dashes |
| A client faking its address | nginx overwrites `X-Forwarded-For`; `TRUST_FORWARDED_FOR=1` is set only when nginx is in front |

Two limits to be clear about:

- The MinIO SHA-256 comes from the same server as the binary. It proves the
  download was not corrupted; it does not prove the server was not replaced.
  Pin a release with `IDRM_MINIO_URL` if that matters to you.
- On Ubuntu 22.04 the deadsnakes PPA is a community source. Its key is
  handled by `add-apt-repository`, not by a fingerprint in this script.

---

## 9. Requirements not about features

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Dependencies of the installer itself | Bash and the Python that ships with Ubuntu. No pip packages |
| NFR-2 | Works on Ubuntu 22.04's Python | Python 3.10 syntax only |
| NFR-3 | Readable by a beginner | Each step states *why* in one sentence; comments explain the reason, not the syntax |
| NFR-4 | Small | Six shell files of 30 to 50 lines, one Python file |
| NFR-5 | Reviewable | A step is one check function and one apply function, next to each other |
| NFR-6 | No hidden state | "Done" is decided by looking at the machine, never by a marker saying a step once ran. The only marker is the content hash of deployed code |

---

## 10. How to use it

### 10.1 A new server, first time

On the server, as a normal user who can use `sudo`:

```bash
sudo apt-get update
```

```bash
sudo apt-get install -y git python3
```

```bash
git clone <your-repo-url> idrm-mvp
```

```bash
cd idrm-mvp
```

See what it would do. Nothing changes:

```bash
bash infra/install.sh
```

Read the plan. Then, for a first bring-up without a domain:

```bash
bash infra/install.sh apply
```

For a public server with a domain name pointing at it:

```bash
bash infra/install.sh apply --profile production --domain idrm.example.org --with-firewall
```

Then add HTTPS ([section 11](#11-https)) and read the admin password:

```bash
sudo grep ADMIN_INITIAL_PASSWORD /etc/idrm/idrm.env
```

Log in as `admin@idrm.local` and change it.

### 10.2 Deploying new code (the small patch)

```bash
git pull
```

```bash
bash infra/install.sh apply --only code --only schema --only services
```

`code` runs only if the checkout differs from what is deployed. `schema`
runs only if there are new migrations. Whenever code, settings, keys or the
schema changed, the two apps are restarted — even when the `services` step
itself had nothing to do.

### 10.3 Checking a server

```bash
bash infra/install.sh verify
```

### 10.4 An accurate plan

`plan` reads a few root-only files (the secrets file, systemd units). If
`sudo` has not been used recently those checks cannot look, and report the
step as "to do". For an exact plan, refresh `sudo` first:

```bash
sudo -v
```

### 10.5 Changing one thing later

| You want to | Do |
|---|---|
| Add a domain to a staging server | `apply --profile production --domain NAME` — `secrets`, `nginx` and `services` run |
| Turn the firewall on | `apply --with-firewall` |
| Regenerate one secret | Delete its line from `/etc/idrm/idrm.env`, then `apply --only secrets --only services`. For the database password, also change it in PostgreSQL |
| Replace the JWT keys | Delete both files in `/etc/idrm/keys/`, then `apply --only keys --only services`. **Signs every user out** |
| Pin MinIO to a release | `IDRM_MINIO_URL=https://… bash infra/install.sh apply` |

---

## 11. HTTPS

The `production` profile sets the console's cookie to "HTTPS only". Until a
certificate is installed, **you cannot log in to the console** — that is the
intended behaviour, not a fault.

Getting a certificate contacts Let's Encrypt and needs your email address, so
the installer leaves it to you. After `apply --domain …` has put nginx in
place, and once the domain's DNS points at the server:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

```bash
sudo certbot --nginx -d idrm.example.org
```

certbot edits the nginx site to add the certificate and installs a timer that
renews it. Because that edit changes the file, the next `plan` will show the
`nginx` step as "to do" and `apply` would write the HTTP-only version back
(keeping certbot's version as a `.bak-…` copy). After certbot, either skip
that step (`--only` the steps you want) or re-run certbot after an `apply`.
This is a known rough edge; see section 15.

---

## 12. Acceptance checks

The install is accepted when all of these hold on a fresh supported machine:

| # | Check | How |
|---|---|---|
| A1 | Plan changes nothing | Run `plan`; `/etc/idrm` and `/opt/idrm` do not exist afterwards |
| A2 | Apply succeeds | `apply` ends with "all checks passed" |
| A3 | Idempotent | A second `apply` prints "Nothing to do" |
| A4 | Health | `verify` exits 0 |
| A5 | Not exposed | From another machine, ports 5432, 6379, 9000, 8000 and 5000 refuse connections |
| A6 | Secrets protected | `ls -l /etc/idrm/idrm.env` shows `-rw-r----- root idrm` |
| A7 | No demo users | With `staging` or `production`: `SELECT count(*) FROM users` is 1 (the admin) |
| A8 | Survives a reboot | After `sudo reboot`, `verify` exits 0 |
| A9 | Patch | Change a file, `apply --only code --only services`; only those two steps run |
| A10 | Wrong target refused | Run another target's script; it stops at preflight |
| A11 | Production guard | With `production`, setting `DASHBOARD_SECRET_KEY=change-me` in the env file makes the services fail to start |

---

## 13. When something goes wrong

| Symptom | Meaning | Do |
|---|---|---|
| `preflight failed: target is … but this machine is …` | Wrong target script | Use `infra/install.sh`, which picks the right one |
| `no target script for this machine` | Unsupported OS, version or processor | See "Adding a target" in section 5 |
| A step fails | The message shows the command and the end of its output | Fix the cause, run `apply` again — finished steps are skipped |
| `step 'X' ran but its check still fails` | The work was done but the result is not what was expected | Read the log in `~/.local/state/idrm-infra/`; `journalctl -u idrm-api -n 50` for a service |
| `another idrm_infra.py run is in progress` | A second run started | Wait for the first |
| MinIO download fails | The download address may have changed | Skip with `--without-minio` (only uploads need it), or set `IDRM_MINIO_URL` |
| A service will not start | Usually a setting | `sudo journalctl -u idrm-api -n 50`; in production the error names the offending setting |

### Undoing it

There is no automatic uninstall. To remove what was added:

```bash
sudo systemctl disable --now idrm-api idrm-dashboard idrm-minio
```

```bash
sudo rm /etc/systemd/system/idrm-*.service && sudo systemctl daemon-reload
```

The next two **destroy data** — the code, the secrets and every uploaded file:

```bash
sudo rm -rf /opt/idrm /etc/idrm
```

```bash
sudo rm -rf /var/lib/idrm
```

The database (`sudo -u postgres dropdb idrm_db`), the PostgreSQL / Redis /
nginx packages and the `idrm` user are left for you to remove deliberately.

---

## 14. What has and has not been tested

| Tested | Where | Result |
|---|---|---|
| Shell syntax of all six scripts | Git Bash | Pass |
| `detect` | Ubuntu 22.04 amd64 under WSL | Correct |
| `plan`, default and `production` + domain + firewall | Same | Lists all steps and the commands; machine unchanged afterwards |
| `--only`, unknown step, missing domain, invalid domain, wrong target, direct call | Same | Each refused with exit code 1 and a clear message |
| `verify` on a machine with nothing installed | Same | Reports failures, exit code 1 |

| **Not tested** | Consequence |
|---|---|
| **`apply`, on any machine** | Every "apply" half of every step is unproven. Expect to fix things on the first real run |
| Ubuntu 24.04, either processor type | Package names are taken from Ubuntu's archive listings, not from a run |
| Any arm64 machine | The MinIO arm64 address and wheel availability are unverified |
| The MinIO download address and its `.sha256sum` companion | Assumed from MinIO's long-standing layout; confirm before relying on it |
| The PostgreSQL key fingerprint | Written from memory of the published key; if it is wrong the step stops safely rather than trusting the key |
| systemd hardening with the real apps | A too-strict option would stop a service from starting; `journalctl` will say which |
| nginx routing, certbot, firewall | Unproven |
| A reboot | Unproven |

**Do the first `apply` on a disposable machine** — a fresh cloud VM or a
snapshot you can roll back — and work through section 12.

---

## 15. Open decisions and known limits

| # | Item | Options |
|---|---|---|
| 1 | certbot rewrites the nginx site, so the `nginx` step then reports "to do" | Have the step accept a certbot-managed file; or generate the HTTPS config ourselves once a certificate exists |
| 2 | MinIO release is "latest" | Pin a version and its hash in each target file for repeatable builds |
| 3 | No backups | Add a step that installs a nightly `pg_dump` timer and says where the files go |
| 4 | No automatic security updates | Add an `unattended-upgrades` step |
| 5 | SSH hardening (keys only, no root login) | Deliberately left out — it can lock you out. Could be an opt-in step with a check that a key login already works |
| 6 | Worker counts are fixed at 2 per app | Derive from CPU count, or make it an option |
| 7 | Single server | Database on its own host needs `DATABASE_URL` supplied instead of generated |
| 8 | The app runs as the database owner | A separate, less-privileged runtime role (see `docs/08-security.md`) |
| 9 | No uninstall command | Add one, with the same plan/apply split |
| 10 | The old scripts in the other four folders | Archive one copy, delete the rest (section 3) |
