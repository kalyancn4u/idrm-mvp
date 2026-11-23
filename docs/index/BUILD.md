# Build, run, deploy — index

Index only: it tells you which document answers a question. It contains no
rules of its own. Open the ONE document you need; for a long one, go to the
section named. Back to [CLAUDE.md](../../CLAUDE.md).

| Document | Answers | ~tokens |
|---|---|---:|
| [01-getting-started.md](../01-getting-started.md) | First run on a development machine | 500 |
| [infra/INFRASTRUCTURE-MASTER-PLAN.md](../infra/INFRASTRUCTURE-MASTER-PLAN.md) | Build a server with `infra/install.sh`. Sections: 5 targets · 7 commands and steps · 10 how to use · 12 acceptance · 13 when it fails | 7,300 |
| [07-operations.md](../07-operations.md) | Running it: monitoring, backups, upgrades, playbooks | 1,400 |
| [10-troubleshooting.md](../10-troubleshooting.md) | A symptom, and what to check | 1,600 |
| [DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md) | Go-live tick list | 2,400 |
| [QUICK_REFERENCE.md](../QUICK_REFERENCE.md) | One page of commands and URLs | 1,900 |

## The one place each fact is written

| Fact | Owner |
|---|---|
| Setting names | `.env.example` |
| Make targets | `Makefile` (`make help`) |
| Server layout, installer steps | INFRASTRUCTURE-MASTER-PLAN.md |
