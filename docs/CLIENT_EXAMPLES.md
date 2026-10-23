# Client Examples

Working code for the three most common integration scenarios. Every
example has been tested against a locally running API.

---

## Scenario 1 — Raise a request as a guest

A citizen with no account needs to request help. The platform returns a
**tracking token** they can use to check status.

### Shell (curl)

```bash
API=http://localhost:8000/api/v1

RESP=$(curl -s -X POST $API/incidents \
  -H 'Content-Type: application/json' \
  -d '{
    "service_type": "water",
    "priority": "high",
    "description": "Village of 200 residents needs drinking water. Last supply was 4 days ago.",
    "location": {"latitude": 17.3850, "longitude": 78.4867}
  }')

echo $RESP | jq

# Save the tracking token
TOKEN=$(echo $RESP | jq -r '.tracking_token')
echo "Tracking: $TOKEN"

# Later — check status
curl -s $API/incidents/track/$TOKEN | jq
```

### Python

```python
import requests

API = "http://localhost:8000/api/v1"

def raise_guest_request(description: str, lat: float, lng: float) -> dict:
    """Raise a help request as a guest. Returns the created incident."""
    r = requests.post(
        f"{API}/incidents",
        json={
            "service_type": "water",
            "priority": "high",
            "description": description,
            "location": {"latitude": lat, "longitude": lng},
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

def check_status(tracking_token: str) -> dict:
    r = requests.get(f"{API}/incidents/track/{tracking_token}", timeout=10)
    r.raise_for_status()
    return r.json()

# Usage
incident = raise_guest_request(
    "Village of 200 needs drinking water.",
    17.3850, 78.4867,
)
print(f"Created: {incident['id']}")
print(f"Status:  {incident['status']}")
print(f"Token:   {incident['tracking_token']}")

# Save the token; use it later
status = check_status(incident["tracking_token"])
print(f"Latest:  {status['status']}")
```

### JavaScript

```javascript
const API = "http://localhost:8000/api/v1";

async function raiseGuestRequest({ description, latitude, longitude }) {
  const r = await fetch(`${API}/incidents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      service_type: "water",
      priority: "high",
      description,
      location: { latitude, longitude },
    }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function checkStatus(trackingToken) {
  const r = await fetch(`${API}/incidents/track/${trackingToken}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// Usage
(async () => {
  const incident = await raiseGuestRequest({
    description: "Village of 200 needs drinking water.",
    latitude: 17.3850,
    longitude: 78.4867,
  });
  console.log("Created:", incident.id);
  console.log("Token:", incident.tracking_token);

  // Save the token in localStorage for later
  localStorage.setItem("idrm.tracking_token", incident.tracking_token);
})();
```

---

## Scenario 2 — Full authenticated workflow

Register, log in, refresh, act.

### Python (a complete client)

```python
"""
A minimal IDRM API client with automatic token refresh.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

API = "http://localhost:8000/api/v1"


@dataclass
class TokenPair:
    access: str
    refresh: str
    expires_at: float

    @property
    def is_expired(self) -> bool:
        # Refresh 60 s early to avoid mid-request expiry
        return time.time() > (self.expires_at - 60)


class IdrmClient:
    def __init__(self) -> None:
        self.tokens: TokenPair | None = None
        self._session = requests.Session()

    # ---- auth ----------------------------------------------------------
    def register(self, email: str, password: str, name: str, role: str = "citizen") -> dict:
        r = self._session.post(
            f"{API}/auth/register",
            json={"email": email, "password": password, "name": name, "role": role},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def login(self, email: str, password: str) -> dict:
        r = self._session.post(
            f"{API}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        r.raise_for_status()
        body = r.json()
        self.tokens = TokenPair(
            access=body["tokens"]["access_token"],
            refresh=body["tokens"]["refresh_token"],
            expires_at=time.time() + body["tokens"]["expires_in"],
        )
        return body["user"]

    def _refresh_if_needed(self) -> None:
        if self.tokens is None:
            raise RuntimeError("Not logged in")
        if not self.tokens.is_expired:
            return
        r = self._session.post(
            f"{API}/auth/refresh",
            json={"refresh_token": self.tokens.refresh},
            timeout=10,
        )
        r.raise_for_status()
        body = r.json()
        self.tokens = TokenPair(
            access=body["access_token"],
            refresh=body["refresh_token"],
            expires_at=time.time() + body["expires_in"],
        )

    # ---- generic request ------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> Any:
        self._refresh_if_needed()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.tokens.access}"
        r = self._session.request(
            method, f"{API}{path}", headers=headers, timeout=10, **kwargs
        )
        if r.status_code == 401:
            # Token rejected even after refresh — probably revoked
            raise PermissionError(r.json())
        r.raise_for_status()
        return r.json()

    # ---- incidents ------------------------------------------------------
    def create_incident(self, description: str, lat: float, lng: float,
                        service: str = "water", priority: str = "medium") -> dict:
        return self._request("POST", "/incidents", json={
            "service_type": service,
            "priority": priority,
            "description": description,
            "location": {"latitude": lat, "longitude": lng},
        })

    def my_incidents(self) -> list[dict]:
        return self._request("GET", "/incidents/mine")["data"]

    def nearby(self, lat: float, lng: float, radius_km: float = 10) -> list[dict]:
        return self._request("GET", "/incidents/nearby", params={
            "latitude": lat, "longitude": lng, "radius_km": radius_km,
        })["data"]

    def accept(self, incident_id: str) -> dict:
        return self._request("POST", f"/incidents/{incident_id}/accept", json={})

    def start(self, incident_id: str) -> dict:
        return self._request("POST", f"/incidents/{incident_id}/start", json={})

    def complete(self, incident_id: str, notes: str = "") -> dict:
        return self._request("POST", f"/incidents/{incident_id}/complete",
                             json={"notes": notes})

    def verify(self, incident_id: str, rating: int, review: str = "") -> dict:
        return self._request("POST", f"/incidents/{incident_id}/verify",
                             json={"rating": rating, "review": review})


# ---- Usage --------------------------------------------------------------
if __name__ == "__main__":
    client = IdrmClient()

    # As a citizen
    client.login("priya.citizen@example.com", "IDRMseed#2026")
    incident = client.create_incident(
        "Client test — 3 households need water.",
        17.40, 78.48,
    )
    print(f"Created: {incident['id']} — status {incident['status']}")

    # Wait a moment, then read your incidents
    for i in client.my_incidents()[:3]:
        print(f"  {i['id'][:8]}  {i['status']:<12}  {i['description'][:50]}…")
```

### JavaScript (browser)

```javascript
class IdrmClient {
  constructor(api = "http://localhost:8000/api/v1") {
    this.api = api;
    this.access = null;
    this.refresh = null;
    this.expiresAt = 0;
  }

  async login(email, password) {
    const r = await fetch(`${this.api}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) throw new Error((await r.json()).error.message);
    const body = await r.json();
    this.access = body.tokens.access_token;
    this.refresh = body.tokens.refresh_token;
    this.expiresAt = Date.now() + body.tokens.expires_in * 1000;
    return body.user;
  }

  async _ensureFresh() {
    if (Date.now() < this.expiresAt - 60_000) return;
    const r = await fetch(`${this.api}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: this.refresh }),
    });
    if (!r.ok) throw new Error("Session expired — please sign in again.");
    const body = await r.json();
    this.access = body.access_token;
    this.refresh = body.refresh_token;
    this.expiresAt = Date.now() + body.expires_in * 1000;
  }

  async _request(method, path, body) {
    await this._ensureFresh();
    const r = await fetch(`${this.api}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.access}`,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (r.status === 401) throw new Error("Session revoked.");
    if (!r.ok) throw new Error((await r.json()).error.message);
    return r.json();
  }

  createIncident(description, lat, lng, service = "water", priority = "medium") {
    return this._request("POST", "/incidents", {
      service_type: service,
      priority,
      description,
      location: { latitude: lat, longitude: lng },
    });
  }

  myIncidents() {
    return this._request("GET", "/incidents/mine").then((b) => b.data);
  }
}

// Usage
(async () => {
  const client = new IdrmClient();
  await client.login("priya.citizen@example.com", "IDRMseed#2026");
  const incident = await client.createIncident(
    "Browser test — 3 households need water.",
    17.40, 78.48,
  );
  console.log("Created:", incident.id, incident.status);

  const list = await client.myIncidents();
  list.slice(0, 3).forEach((i) =>
    console.log(`${i.id.slice(0, 8)}  ${i.status.padEnd(12)}  ${i.description.slice(0, 50)}`)
  );
})();
```

---

## Scenario 3 — Provider workflow (accept, start, complete)

### Python

```python
from client import IdrmClient   # from Scenario 2

client = IdrmClient()
client.login("smilinghearts@ngo.example", "IDRMseed#2026")

# See what's near you
nearby = client.nearby(lat=17.38, lng=78.48, radius_km=15)
if not nearby:
    print("No incidents nearby.")
else:
    incident = nearby[0]
    print(f"Accepting {incident['id'][:8]}: {incident['description'][:60]}")

    # Accept → start → complete
    client.accept(incident["id"])
    client.start(incident["id"])
    client.complete(incident["id"], notes="Delivered 200 water packets.")

    print("Done.")
```

---

## Scenario 4 — Coordinator using the console

The dashboard is HTML, not JSON — a coordinator uses the browser, not code.
But the dispatch workflow is scriptable via the API for coordinators.

```bash
API=http://localhost:8000/api/v1

# Log in as coordinator
TOKENS=$(curl -s -X POST $API/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"coord.hyd@idrm.local","password":"IDRMseed#2026"}')
ACCESS=$(echo $TOKENS | jq -r '.tokens.access_token')

# See the dispatch board
curl -s -H "Authorization: Bearer $ACCESS" $API/dispatch/board | jq
```

```json
{
  "incidents": [
    {
      "id": "…",
      "service_type": "water",
      "priority": "medium",
      "status": "approved",
      "description": "Water supply has been cut…"
    }
  ],
  "active_assignments": [],
  "pending_offers": []
}
```

**Dispatch a unit:**

```bash
INCIDENT=...   # from the board
UNIT=21000000-0000-4000-8000-000000000001   # Food Truck 01

curl -s -X POST $API/dispatch/assign \
  -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' \
  -d "{\"incident_id\":\"$INCIDENT\",\"unit_id\":\"$UNIT\",\"note\":\"Dispatched via API\"}" | jq
```

**Offer to a volunteer:**

```bash
USER=10000000-0000-4000-8000-000000000009   # Ravi Teja

curl -s -X POST $API/dispatch/offer \
  -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' \
  -d "{\"incident_id\":\"$INCIDENT\",\"user_id\":\"$USER\",\"ttl_minutes\":15}" | jq
```

---

## Postman collection

Save this as `idrm.postman_collection.json` and import into Postman:

```json
{
  "info": {
    "name": "IDRM MVP",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    { "key": "api", "value": "http://localhost:8000/api/v1" },
    { "key": "access", "value": "" },
    { "key": "refresh", "value": "" }
  ],
  "item": [
    {
      "name": "Auth",
      "item": [
        {
          "name": "Login",
          "request": {
            "method": "POST",
            "url": "{{api}}/auth/login",
            "header": [{ "key": "Content-Type", "value": "application/json" }],
            "body": {
              "mode": "raw",
              "raw": "{\"email\":\"admin@idrm.local\",\"password\":\"Admin#2026\"}"
            }
          },
          "event": [
            {
              "listen": "test",
              "script": {
                "exec": [
                  "const b = pm.response.json();",
                  "pm.collectionVariables.set('access', b.tokens.access_token);",
                  "pm.collectionVariables.set('refresh', b.tokens.refresh_token);"
                ]
              }
            }
          ]
        },
        {
          "name": "Refresh",
          "request": {
            "method": "POST",
            "url": "{{api}}/auth/refresh",
            "header": [{ "key": "Content-Type", "value": "application/json" }],
            "body": {
              "mode": "raw",
              "raw": "{\"refresh_token\":\"{{refresh}}\"}"
            }
          }
        }
      ]
    },
    {
      "name": "Incidents",
      "item": [
        {
          "name": "List mine",
          "request": {
            "method": "GET",
            "url": "{{api}}/incidents/mine",
            "header": [{ "key": "Authorization", "value": "Bearer {{access}}" }]
          }
        },
        {
          "name": "Create",
          "request": {
            "method": "POST",
            "url": "{{api}}/incidents",
            "header": [
              { "key": "Content-Type", "value": "application/json" },
              { "key": "Authorization", "value": "Bearer {{access}}" }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\"service_type\":\"water\",\"priority\":\"medium\",\"description\":\"Test from Postman.\",\"location\":{\"latitude\":17.40,\"longitude\":78.48}}"
            }
          }
        }
      ]
    }
  ]
}
```

---

## Language-specific notes

### Python
- Use `requests.Session` for connection pooling.
- Refresh 60 seconds before expiry to avoid mid-request races.
- Always set a timeout — a slow API can hang a client.

### JavaScript
- Use `fetch` with an `AbortController` for timeouts.
- Refresh proactively if you know the TTL.
- Never store tokens in `localStorage` on a shared machine — prefer memory
  or `sessionStorage` with a clear sign-out.

### Shell
- Use `jq` for parsing — it is available almost everywhere.
- Never echo tokens into a public terminal or a log.
- Prefer environment variables over hard-coded credentials.

---

## Where to get more

- Full endpoint list: [04-api-reference.md](04-api-reference.md)
- Auth details: [13-auth-and-sessions.md](13-auth-and-sessions.md)
- Governance: [12-governance.md](12-governance.md)
- Interactive API docs: http://localhost:8000/docs
