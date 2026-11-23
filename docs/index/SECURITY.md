# Security — index

Index only: it tells you which document answers a question. It contains no
rules of its own. Open the ONE document you need; for a long one, go to the
section named. Back to [CLAUDE.md](../../CLAUDE.md).

| Document | Answers | ~tokens |
|---|---|---:|
| [08-security.md](../08-security.md) | Threats, controls, permission tables, limits of audit immutability | 1,600 |
| [SECURITY_VERIFICATION.md](../SECURITY_VERIFICATION.md) | 13 copy-paste tests that prove each control | 2,400 |
| [design/DATA-DESIGN.md](../design/DATA-DESIGN.md) §4, §9 | Data security layers, DB roles, STRIDE for data, breach response, backups and recovery targets | 11,000 |
| [design/PRIVACY-FIRST-DATA-DESIGN.md](../design/PRIVACY-FIRST-DATA-DESIGN.md) | ACCEPTED (ADR-0015), not built — privacy design: hide by default, reveal by need; threats §11; DPDP §14; owner decisions §16 | 9,000 |

## The one place each fact is written

| Fact | Owner |
|---|---|
| Password hashing, permission matrices | 08-security.md |
| Ownership checks | `app/core/authz.py` |
