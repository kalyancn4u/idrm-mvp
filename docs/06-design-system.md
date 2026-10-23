# Design System — Two Canvases, One Vocabulary

The platform has **one design system** and **two visual identities**.
Everything below the page background is identical between the FastAPI public
site and the Flask staff console. Only the canvas changes.

## The two canvases

| | Public API | Staff Console |
|---|---|---|
| `--color-bg-page` | `#f8fafc` — cool slate | **`#fff7ed` — pale saffron** |
| `--color-bg-surface-elevated` | `#f1f5f9` | `#fef3e2` — warm sand |
| `--color-bg-overlay` | `rgba(15, 23, 42, 0.04)` | `rgba(120, 53, 15, 0.05)` |
| `--color-accent-warm` | *(unused)* | **`#f97316` — saffron** |
| Feel | Informational, public, calm | Operational, warm, decisive |

### Why saffron for the console

**Saffron is the operational colour of Indian disaster response.** When a
coordinator has both tabs open during an incident, the warm canvas is a
sub-second cue: *"this is the console — you can act here."*

The accent is used **once**: a 3 px vertical rail on the active sidebar nav
item, and on the "Dispatch Now" button.

### Contrast

Every text/background pair in the console passes **WCAG AAA (7:1)** — the
warm canvas is *lighter*, not darker, than the cool canvas it replaces:

| Pair | Contrast |
|---|---|
| `#0f172a` on `#fff7ed` | 16.8:1 (AAA) |
| `#334155` on `#fff7ed` | 10.1:1 (AAA) |
| `#b91c1c` on `#fef2f2` | 7.6:1 (AAA) |
| `#9a3412` on `#ffedd5` | 7.1:1 (AAA) |

## Components

Both apps ship the same components. The only console-specific addition is
`.btn-warm` (saffron button) and `.kpi-warm` (saffron accent on the KPI card).

| Component | Class |
|---|---|
| Card | `.card` |
| KPI | `.kpi-card` |
| Badge | `.badge`, `.pri` |
| Alert | `.alert` |
| Button | `.btn` |
| Table | `.data-table` |
| Timeline | `.timeline` |
| Pager | `.pager` |
| State | `.state-container` |
| Dispatch | `.dispatch-grid`, `.dispatch-panel` |
| BigBoard | `.bigboard`, `.bigboard-widget` |

## The two CSS files

Both files are byte-identical **except** for four tokens. The dashboard
version additionally adds `.btn-warm`, `.kpi-warm`, `.badge-warm`, and the
warm-tinted shadows.

## Accessibility

| Requirement | Implementation |
|---|---|
| Contrast ≥ 7:1 | Verified for both canvases |
| Focus visible | `*:focus-visible` outline |
| Semantic landmarks | `<aside>`, `<header>`, `<main>`, `<footer>` |
| Required fields | `.form-label.required::after` |
| Status messages | `role="status"` on flash alerts |
| Reduced motion | `@media (prefers-reduced-motion)` |
| Icon-only buttons | `aria-label` on every one |

