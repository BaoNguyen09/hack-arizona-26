# AGENT.md — context for AI assistants (Lumen / Hack Arizona 2026)

## What this repo is

**Lumen** — renewable energy **cost-optimization** platform: heatmap + site detail from weather, wholesale prices, carbon intensity, and infrastructure. Stack: **FastAPI** backend, **React + Vite + Deck.gl + MapLibre** frontend, **local-first** data under `data/`.

- **Product intent:** composite score per grid cell (LCOE / revenue / carbon), physics-based solar + wind, optional LLM site briefs, NL query later.
- **Performance target:** pre-compute heavy work; API stays fast (target ~200ms after scenario change per product docs).

## Where things live

| Path | Role |
|------|------|
| `backend/app/` | FastAPI app: `api/`, `core/`, `schemas/`, `services/`, `main.py` |
| `backend/tests/` | Pytest |
| `frontend/` | React TS client, map + panels |
| `data/raw`, `data/processed`, `data/reference` | Ingests + artifacts (gitkeep where empty) |
| `scripts/`, `notebooks/`, `infra/` | Jobs, experiments, deploy stubs |
| `docs/` | `architecture.md`, `backlog.md`, `issues/`, `ISSUE18_WORK_ORDER.md` |
| `.github/` | CI, issue/PR templates, `BACKEND_TEAM.md` |

Deeper design: [docs/architecture.md](docs/architecture.md) · product/backlog: [docs/backlog.md](docs/backlog.md) · human README: [README.md](README.md).

## Team ↔ code ownership (merge boundaries)

| Person | Owns (primary) |
|--------|----------------|
| **Duc** | Data pipeline: `backend/app/data/` (or ingestion paths your branch uses), `data/raw` / `data/processed`, `scripts` for download/precompute |
| **John** | Modeling + scoring: `backend/app/engine/` (or equivalent), engine tests |
| **Bao** | API + LLM: `backend/app/api/`, `schemas/`, `services/` (briefs, query) |
| **Shane** | Geo + **integration** + smoke QA: `backend/app/geo/`, **`backend/app/main.py`**, top-level app wiring, `backend/tests` smoke |

**Rule:** After scaffold is stable, only **Shane** edits `main.py` / router wiring unless the team agrees otherwise. Everyone else: importable modules + PRs. Details: [.github/BACKEND_TEAM.md](.github/BACKEND_TEAM.md).

## GitHub work tracking

- **Epic / tracker #18** (backend MVP checklist + child issues #1–#17): [issue #18](https://github.com/BaoNguyen09/hack-arizona-26/issues/18) (repo: `BaoNguyen09/hack-arizona-26` if URL changes, search “Lumen backend MVP” tracker).
- **Parallel work + dependency order:** [docs/ISSUE18_WORK_ORDER.md](docs/ISSUE18_WORK_ORDER.md).
- **Assignee names → issues:** [docs/ASSIGNEES.md](docs/ASSIGNEES.md).

Hard sync points (short): **#2** grid fixture → unlocks much; **#6** scoring → real heatmap; **#7** geo → full site; **#8** precompute last among MVP pipeline pieces.

## Commands (local)

```bash
make install     # pip install -r requirements.txt
make api         # uvicorn backend.app.main:app --reload
make test        # pytest backend/tests
make frontend    # Vite dev server
make lint        # ruff (if installed)
```

Copy `.env.example` → `.env` when wiring APIs / keys. CI: [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Agent behavior hints

1. **Respect folder ownership** above — big diffs in someone else’s lane need coordination.
2. **Prefer small PRs** per issue; don’t “finish Lumen” in one shot unless asked.
3. **Data:** don’t commit huge binaries; use samples + docs for full URLs.
4. **Frontend** and **backend** may disagree on route paths — check `backend/app/api` / `main.py` and frontend fetch URLs before assuming.
5. **Issue bodies** in `docs/issues/` are design references; **#18** tracker is the current hackathon split.

## Doc index (quick)

- Architecture: [docs/architecture.md](docs/architecture.md)
- Issue epics: [docs/issues/](docs/issues/)
- PR template: [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)

Last updated: align this file when ownership or top-level layout changes.
