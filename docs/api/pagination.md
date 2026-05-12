# Paginacao canonica (Sprint 2 Track Page + Sprint 3 Page-Migration)

Contrato unico de paginacao para listagens da API Cannab'IA. Helper:
`src/web/pagination.py`. Tipo TS: `Paginated<T>` em `frontend/lib/types.ts`.

> **Sprint 3 Page-Migration (este PR):**
> - Tier-2 (governance, evidence, medical_record, patient_timeline) migrado.
> - `PaginatedResult<T>` + `ApiListMeta` removidos do frontend (mismatch
>   critico identificado em Phase 0 — zero consumers reais).
> - `limit > MAX_LIMIT` agora retorna **HTTP 400 `invalid_limit`** (era
>   clamp silencioso). Permite retry inteligente no cliente.
> - `?legacy=1` agora emite **headers `Deprecation: true` + `Sunset:
>   2026-08-01`** + `console.warn` no helper `request()` do frontend.
>   Removal planejada na Sprint 4.

## Contrato

### Query params

| Param            | Tipo    | Default | Notas                                                                |
| ---------------- | ------- | ------- | -------------------------------------------------------------------- |
| `limit`          | int     | `50`    | Max `200`. **Sprint 3:** `>200 -> HTTP 400 invalid_limit`.           |
| `offset`         | int     | `0`     | Offset-based.                                                        |
| `include_total`  | `0\|1`  | `0`     | Opt-in pra `COUNT(*)`. Sem ele, `total: null`.                       |
| `legacy`         | `0\|1`  | `0`     | **DEPRECATED** (Sunset 2026-08-01). Retorna lista nua + headers.     |
| `paginated`      | `0\|1`  | `0`     | Tier-2 opt-in (preserva shape Sprint 1 default). Tier-1 ja default.  |
| `before_id`      | int     | -       | **Cursor-based** (`patient_timeline` apenas).                        |

`limit < 1` ou `offset < 0` -> HTTP `422 validation_error`.

### Envelope (response body)

```jsonc
{
  "items": [ /* T[] */ ],
  "total": 1234 | null,         // null se include_total=0 (default)
  "limit": 50,
  "offset": 0,
  "has_more": true,             // heuristica LIMIT+1 OU exato com total
  "next_cursor": 4 | null       // SO em cursor-based (timeline)
}
```

`has_more`:
- Com `total` conhecido: `(offset + items.length) < total`.
- Sem `total`: backend pede `LIMIT (limit + 1)` e descarta o extra
  (helper `apply_limit_plus_one` / alias `LIMIT_PLUS_ONE_TRICK`).

### Cursor-based (`patient_timeline`)

Feed temporal usa cursor estilo `messages` (precedente Sprint 1):

```
GET /api/v1/patients/<id>/timeline?paginated=1&limit=20
  -> { items: [...20 eventos descendentes...], has_more: true, next_cursor: <id_ultimo> }

GET /api/v1/patients/<id>/timeline?before_id=<next_cursor>&limit=20
  -> proxima pagina (eventos com id < next_cursor)
```

Motivacao: timeline tem appends frequentes; offset-puro daria drift
entre paginas. Cursor garante consistencia mesmo com inserts simultaneos.

### Deprecation (`?legacy=1`)

A partir da Sprint 3, `?legacy=1`:

1. Server-side: `logger.warning("pagination.legacy_used endpoint=...")`.
2. Response headers: `Deprecation: true`, `Sunset: Sun, 01 Aug 2026 00:00:00 GMT`.
3. Frontend (`request()` em `lib/api.ts`): detecta `Deprecation` na
   response e emite `console.warn("[API] endpoint X usa ?legacy=1
   deprecated — migrar antes de Sprint 4")`.

**Sprint 4 plan:** remover o branch `if legacy_mode` dos repos +
remover `bare_legacy_response` do helper.

## Endpoints migrados (Sprint 2 Tier-1)

| Endpoint                            | Repo                                                     | Notas                              |
| ----------------------------------- | -------------------------------------------------------- | ---------------------------------- |
| `GET /api/v1/appointments`          | `appointment_repository.list_appointments`               | Envelope default; `?legacy=1` deprecated. |
| `GET /api/v1/attendances`           | `anamnesis_repository.list_reports`                      | Envelope default; `?legacy=1` deprecated. |
| `GET /api/v1/conversations`         | `conversation_repository.list_conversations`             | Envelope default; `?legacy=1` deprecated. |
| `GET /api/v1/admin/ai-metrics`      | `ai_audit_repository.get_recent_ai_logs_filtered`        | `?paginated=1` -> envelope em `recent_logs`. |

## Endpoints migrados (Sprint 3 Tier-2)

| Endpoint                                           | Repo                                                       | Notas                                                |
| -------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------- |
| `GET /api/v1/governance/documents?paginated=1`     | `governance_repository.list_institutional_documents`       | Compat path mantido (callers internos: dossier).     |
| `GET /api/v1/governance/rts?paginated=1`           | `governance_repository.list_technical_responsibles`        | Idem.                                                |
| `GET /api/v1/patients/<id>/medical-record?paginated=1` | `medical_record_repository.list_patient_record_entries` | Compat path **mandatorio** (atendimentos.py:47-48).  |
| `GET /api/v1/patients/<id>/timeline?paginated=1`   | `patient_timeline_repository.list_patient_events`          | **Cursor-based** via `?before_id`.                   |
| (interno) `evidence_repository.list_treatment_plans_by_condition` | -                                          | Apenas paginavel internamente; consumido por service.|

`governance` e `medical-record` mantem o shape Sprint 1 como **default**
pra preservar callers internos (governance_service, governance_dossier,
atendimentos route, `_build_attendance_detail`). `?paginated=1` ativa o
envelope explicitamente.

## Padrao de uso

### Backend (route)

```python
from src.web.pagination import bare_legacy_response, paginated_response, parse_pagination
from src.web.routes.api_v1 import _apply_deprecation_headers, _pagination_error

try:
    limit, offset, include_total, legacy = parse_pagination(request)
except ValueError as exc:
    return _pagination_error(exc)   # mapeia >MAX -> 400 invalid_limit

if legacy:
    return _apply_deprecation_headers(
        _success(bare_legacy_response(repo.list_x()))
    )

result = repo.list_x(limit=limit, offset=offset, include_total=include_total)
return _success(paginated_response(
    result["items"], limit=limit, offset=offset,
    total=result["total"], has_more=result["has_more"],
))
```

### Backend (repo com compat path)

```python
def list_x(*, limit=None, offset=0, include_total=False):
    if limit is None:
        # compat path — caller interno legacy espera list[dict]
        return rows
    # paginado — caller HTTP espera envelope
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

### Frontend (consumer Sprint 3)

```ts
import { listAttendances } from "@/lib/api";
import type { Paginated, AttendanceListItem } from "@/lib/types";

// Primeira pagina
const env: Paginated<AttendanceListItem> = await listAttendances({
  limit: 50, offset: 0,
});
console.log(env.items, env.has_more, env.total);

// "Carregar mais"
const next = await listAttendances({ limit: 50, offset: env.items.length });
```

`request()` em `lib/api.ts` detecta header `Deprecation` e emite
`console.warn` automaticamente quando o endpoint usa `?legacy=1`.

## Decisoes coordenador

### Sprint 2 (Tier-1)

| ID         | Decisao                                                                              |
| ---------- | ------------------------------------------------------------------------------------ |
| Q-Page-1   | Hibrido offset/cursor — Sprint 2 so offset; cursor ja existe em `messages`.          |
| Q-Page-2   | Envelope no body (nao via headers).                                                  |
| Q-Page-3   | `default=50` + `?legacy=1` (escape hatch 1 sprint).                                  |
| Q-Page-4   | Tier-1+Tier-2 escopo total; Sprint 2 entregou apenas Tier-1.                         |
| Q-Page-5   | Sprint 2: clamp + warning. **Sprint 3: HTTP 400 invalid_limit.**                     |
| Q-Page-6   | `?include_total=1` opt-in; sem ele, `total: null` + heuristica LIMIT+1.              |
| Q-Page-7   | `dashboard_repository` fora do escopo (queries diferentes).                          |

### Sprint 3 (Page-Migration)

| ID         | Decisao                                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------------------- |
| Q-PM-0     | **`Paginated<T>` canonico**; remover `PaginatedResult<T>` + `ApiListMeta` (zero consumers reais).        |
| Q-PM-1     | `error.code = "invalid_limit"` (especifico, permite retry inteligente).                                  |
| Q-PM-2     | PR unico (escopo total cabe em 1 sprint).                                                                |
| Q-PM-3     | `patient_timeline` cursor-based via `before_id` (correto pra feed temporal; messages tem precedente).    |
| Q-PM-4     | Deprecacao VISIVEL — server log + headers + `console.warn` frontend.                                     |
| Q-PM-5     | Tier-3 (payment, regulatory_reporting, adverse_event) fica divida Sprint 4.                              |
| Q-PM-6     | Repos com compat path: `limit=None -> list[dict]` (callers internos), `limit=int -> dict envelope`.      |

## Sprint 4 plan

1. **Tier-3 (3 endpoints)**:
   - `payment_repository.list_payments`
   - `regulatory_reporting_repository.list_reports`
   - `adverse_event_repository.list_events`
2. **Remover `?legacy=1`** completamente:
   - Date de remocao: **2026-08-01** (Sunset).
   - Apaga `bare_legacy_response`, `if legacy_mode` em todos os repos.
   - Apaga `_apply_deprecation_headers` helper.
3. **Remover `paginated=1` opt-in**: mover Tier-2 default para envelope
   (aproveita Sprint 4 quebrar contrato pra simplificar API).
4. **dashboard_repository**: avaliar migracao (Q-Page-7 marcou fora-de-escopo;
   reavaliar se ainda).
