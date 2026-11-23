# API, tokens, sessions — index

Index only: it tells you which document answers a question. It contains no
rules of its own. Open the ONE document you need; for a long one, go to the
section named. Back to [CLAUDE.md](../../CLAUDE.md).

| Document | Answers | ~tokens |
|---|---|---:|
| [04-api-reference.md](../04-api-reference.md) | Every endpoint, who may call it, error format | 2,200 |
| [13-auth-and-sessions.md](../13-auth-and-sessions.md) | Tokens, lifetimes, refresh, revocation | 800 |
| [CLIENT_EXAMPLES.md](../CLIENT_EXAMPLES.md) | Working client code. Sections: Scenario 1 guest · 2 authenticated · 3 provider · 4 coordinator | 4,000 |

## The one place each fact is written

| Fact | Owner |
|---|---|
| Endpoint list | 04-api-reference.md (the live list is `/docs` on a running API) |
| Token lifetimes, role list | 13-auth-and-sessions.md |
| Incident states and who may move them | `shared/lifecycle.py`, explained in ADR-0014 |
