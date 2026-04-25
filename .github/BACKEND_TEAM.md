# Lumen backend — team lanes (merge boundaries)

| Who | Focus | Owns (primary) |
|-----|--------|----------------|
| **Duc** | Data pipeline | `backend/app/data/`, `backend/scripts/`, `data/raw/`, `data/processed/` |
| **John** | Model + scoring | `backend/app/engine/`, `backend/tests/engine/` |
| **Bao** | API + LLM briefs / query | `backend/app/api/`, `backend/app/schemas/`, `backend/app/services/` (briefs, query parser) |
| **Shane** | Geospatial + integration + QA | `backend/app/geo/`, `backend/app/main.py`, `backend/tests/` (smoke), demo fixtures |

**Rule:** After the scaffold lands, only **Shane** should change `backend/app/main.py` and top-level app wiring unless the team syncs.

See [docs/ISSUE18_WORK_ORDER.md](../docs/ISSUE18_WORK_ORDER.md) for **what you can do in parallel** vs **when you must wait**.
