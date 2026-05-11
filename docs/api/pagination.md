# Paginacao canonica (Sprint 2 Track Page)

Contrato unico de paginacao para listagens da API Cannab'IA. Helper:
`src/web/pagination.py`. Tipo TS: `Paginated<T>` em `frontend/lib/types.ts`.

## Contrato

### Query params

| Param            | Tipo  | Default | Notas                                                           |
| ---------------- | ----- | ------- | --------------------------------------------------------------- |
| `limit`          | int   | `50`    | Max `200`. Acima disso: clamp + warning server-side.            |
| `offset`         | int   | `0`     | Offset-based. (Cursor existe so em `messages`.)                 |
| `include_total`  | `0|1` | `0`     | Opt-in pra `COUNT(*)`. Sem ele, `total: null`.                  |
| `legacy`         | `0|1` | `0`     | Escape hatch (1 sprint): retorna lista nua sem envelope.        |

`limit < 1` ou `offset < 0` -> HTTP `422 validation_error`.

### Envelope (response body)

```jsonc
{
  "items": [ /* T[] */ ],
  "total": 1234 | null,        // null se include_total=0 (default)
  "limit": 50,
  "offset": 0,
  "has_more": true             // heuristica LIMIT+1 OU exato com total
}
```

`has_more`:
- Com `total` conhecido: `(offset + items.length) < total`.
- Sem `total`: backend pede `LIMIT (limit + 1)` e descarta o extra
  (helper `apply_limit_plus_one` / alias `LIMIT_PLUS_ONE_TRICK`).

### Compat path (`?legacy=1`)

Retorna **lista nua** (Sprint 1 shape). Disponivel por **1 sprint**;
removido na Sprint 3.

## Endpoints migrados (Sprint 2 Tier-1)

| Endpoint                            | Repo                                                     | Notas                              |
| ----------------------------------- | -------------------------------------------------------- | ---------------------------------- |
| `GET /api/v1/appointments`          | `appointment_repository.list_appointments`               | Envelope default; `?legacy=1` OK.  |
| `GET /api/v1/attendances`           | `anamnesis_repository.list_reports`                      | Envelope default; `?legacy=1` OK.  |
| `GET /api/v1/conversations`         | `conversation_repository.list_conversations`             | Envelope default; `?legacy=1` OK.  |
| `GET /api/v1/admin/ai-metrics`      | `ai_audit_repository.get_recent_ai_logs_filtered`        | Compat por default; `?paginated=1` ativa envelope dentro de `recent_logs`. |

`/admin/ai-metrics` e composto (`summary + recent_logs + filters`); por isso o
envelope so se ativa via `?paginated=1` pra preservar 100% do shape Sprint 1.

## Padrao de uso

### Backend (route)

```python
from src.web.pagination import bare_legacy_response, paginated_response, parse_pagination

try:
    limit, offset, include_total, legacy = parse_pagination(request)
except ValueError as exc:
    return _error("validation_error", str(exc), 422)

if legacy:
    return _success(bare_legacy_response(repo.list_x()))

result = repo.list_x(limit=limit, offset=offset, include_total=include_total)
return _success(paginated_response(
    result["items"], limit=limit, offset=offset,
    total=result["total"], has_more=result["has_more"],
))
```

### Backend (repo)

```python
def list_x(*, limit=None, offset=0, include_total=False):
    if limit is None:
        # compat path
        ...
        return rows
    # paginado
    total = None
    if include_total:
        total = int(cur.execute("SELECT COUNT(*) ...").fetchone()["n"])
    fetch_n = limit if include_total else limit + 1
    cur.execute("SELECT ... LIMIT %s OFFSET %s", (..., fetch_n, offset))
    rows = cur.fetchall()
    if include_total:
        items = rows
        has_more = (offset + len(items)) < (total or 0)
    else:
        from src.web.pagination import apply_limit_plus_one
        items, has_more = apply_limit_plus_one(rows, limit)
    return {"items": items, "total": total, "has_more": has_more}
```

### Frontend (consumer — divida Sprint 3)

```ts
import type { Paginated, Appointment } from "@/lib/types";

const res: Paginated<Appointment> = await fetch(
  "/api/v1/appointments?limit=50&offset=0"
).then(r => r.json()).then(j => j.data);

console.log(res.items, res.has_more, res.total);
```

## Decisoes (coordenador Sprint 2)

| ID         | Decisao                                                                              |
| ---------- | ------------------------------------------------------------------------------------ |
| Q-Page-1   | Hibrido offset/cursor — Sprint 2 so offset; cursor ja existe em `messages`.          |
| Q-Page-2   | Envelope no body (nao via headers).                                                  |
| Q-Page-3   | `default=50` + `?legacy=1` (escape hatch 1 sprint).                                  |
| Q-Page-4   | Tier-1+Tier-2 escopo total; **Sprint 2 entregou apenas Tier-1**.                     |
| Q-Page-5   | Clamp `limit > 200` + log warning (Sprint 3 vira HTTP 400).                          |
| Q-Page-6   | `?include_total=1` opt-in; sem ele, `total: null` + heuristica LIMIT+1.              |
| Q-Page-7   | `dashboard_repository` fora do escopo (queries diferentes).                          |

## Divida Sprint 3

1. **Tier-2 (4 endpoints)**: aplicar mesmo padrao em
   - `governance_repository.list_institutional_documents`
   - `evidence_repository.list_*` (a queryless mais usada)
   - `medical_record_repository.list_patient_record_entries`
   - `patient_timeline_repository.list_patient_events`
2. **Frontend consumers**: migrar todos os fetches que hoje esperam `Type[]`
   pra `Paginated<Type>` (Sprint 2 so adicionou o tipo, sem trocar nenhum
   consumer).
3. **`?legacy=1` removal**: Sprint 3 deve remover o flag e o branch de
   compat dos repos (limpar o `if limit is None`).
4. **Limit > 200**: Sprint 3 vira HTTP 400 (hoje so faz clamp + warning).
