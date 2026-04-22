# Runbook Operacional — Anchoring SCC (F5.7)

**Escopo:** operação diária do pipeline de ancoragem em blockchain pública do Sandbox Compliance Core. Complementa o backbone técnico descrito em [docs/26_BLOCKCHAIN_ANCHORING_PROTOCOL.md](26_BLOCKCHAIN_ANCHORING_PROTOCOL.md).

**Decisão de rede (2026-04-21):** Polygon como provider primário (contrato [`SandboxAnchor`](../contracts/SandboxAnchor.sol)); Bitcoin OTS disponível como alternativa auditável via `ANCHORING_PROVIDER=ots`. Seleção via env var, ver §3.

---

## 1. Cadência recomendada

| Escopo | Frequência | Gatilho |
|---|---|---|
| `tenant` | 1×/dia (02:00 UTC) | cron scheduled |
| `project` | semanal (domingo 03:00 UTC) | cron scheduled |
| `global` | diário (04:00 UTC) | cron scheduled |
| Ad-hoc | sob demanda | admin via API interna |

O cron dispara `create_anchor(tenant_id, covered_from, covered_until, ...)` para cada tenant ativo. Em Polygon, a confirmação leva ~2–3 min; o job de upgrade (§4) promove `pending → confirmed` depois.

---

## 2. Pré-requisitos de infraestrutura

### 2.1 Variáveis de ambiente

```env
# Provider primário
ANCHORING_PROVIDER=polygon

# Polygon (F5.4)
POLYGON_NETWORK=amoy                              # ou 'mainnet'
POLYGON_RPC_URL=https://rpc-amoy.polygon.technology
POLYGON_DEPLOYER_PRIVATE_KEY=0x...                # multi-sig recomendado em prod
POLYGON_SANDBOX_ANCHOR_ADDRESS=0x...              # populado após deploy

# OTS fallback (F5.3) — só necessário se rodar com provider=ots
# (nenhuma env extra além do pacote opentimestamps-client do PyPI)
```

### 2.2 Dependências Python

```bash
pip install web3 opentimestamps-client
```

Ambas são **opcionais** — o código faz import lazy. CI sem as libs continua verde, mas o upgrade real só funciona com elas instaladas.

### 2.3 Deploy do contrato

Ver [contracts/README.md](../contracts/README.md). Resumo:

```bash
# Amoy (testnet)
forge build
forge create contracts/SandboxAnchor.sol:SandboxAnchor \
  --rpc-url $POLYGON_RPC_URL \
  --private-key $POLYGON_DEPLOYER_PRIVATE_KEY
# capture address da saída; exporte como POLYGON_SANDBOX_ANCHOR_ADDRESS
```

Depois **verificar no Polygonscan** — é requisito regulatório.

---

## 3. Alternância entre providers

Trocar de Polygon → OTS (fallback):

```bash
export ANCHORING_PROVIDER=ots
# restart do serviço / recarga de env — sem recompilar
```

Uso típico desse fallback:

- Polygon RPC fora do ar por > 15 min
- Custo de gas Polygon anormalmente alto (raro, mas possível)
- Necessidade de prova Bitcoin-grade para um documento específico (ex.: parecer final do experimento)

A decisão é **reversível** — ancoragens já feitas em uma rede permanecem válidas quando o provider muda.

---

## 4. Job de upgrade (pending → confirmed|failed)

### 4.1 Quando rodar

A cada **5 minutos** (cron). A cadência baixa é segura pois:
- O job é idempotente (skipped quando já `confirmed`/`failed`).
- `MIN_AGE_SECONDS = 5 * 60` evita polling inútil antes do tempo de confirmação.
- Polygon confirma ~3 min; OTS ~1 h.

### 4.2 Como invocar

Script de cron (cria se não existir):

```python
# scripts/anchor_upgrade_cron.py
from src.services.anchor_upgrade_service import run_upgrade_sweep

if __name__ == "__main__":
    outcomes = run_upgrade_sweep()
    for o in outcomes:
        print(f"{o.anchor_id} {o.previous_status} -> {o.new_status}")
```

Agendamento:

```cron
*/5 * * * * /path/to/venv/bin/python /path/to/repo/scripts/anchor_upgrade_cron.py
```

Em systemd alternativo:

```ini
# /etc/systemd/system/anchor-upgrade.timer
[Timer]
OnCalendar=*:0/5

[Install]
WantedBy=timers.target
```

### 4.3 Tratamento de estados

| Status anterior | Resultado | Ação |
|---|---|---|
| `pending` (< 5 min) | `skipped` | aguardar próximo run |
| `pending` + probe OK | `confirmed` | `verified_at` + `block_number` gravados |
| `pending` + probe err (< 48 h) | `still_pending` | re-try nos próximos runs |
| `pending` + probe err (≥ 48 h) | `failed` | alerta ops — ver §5.3 |
| `confirmed` | `skipped` | não-op |
| `failed` | `skipped` | não-op |

Limite `MAX_AGE_FAIL_SECONDS = 48 * 3600` (48 h) é conservador para Polygon e razoável para OTS (considerando reorg de Bitcoin).

---

## 5. Cenários de incidente

### 5.1 Reorg de Bitcoin (OTS)

**Sintoma:** anchor em status `confirmed` mas com `block_number` que sumiu do histórico Bitcoin.

**Detecção:** job de auditoria semanal re-valida `proof_hash` contra o arquivo `.ots` atualizado. Divergência → alerta.

**Mitigação:** o OTS protocol é robusto a reorgs de 1-2 blocos. Para reorgs mais profundos (raros), re-gerar a ancoragem com o mesmo `merkle_root` em nova transação. O histórico anterior fica em `verification_status='failed'` com nota explicativa em `proof_uri`.

### 5.2 RPC Polygon fora do ar

**Detecção:** `run_upgrade_sweep` retorna outcomes com `error` contendo timeout/connection refused em série.

**Mitigação imediata:**
1. Alternar para `ANCHORING_PROVIDER=ots` (§3).
2. Verificar [status.polygon.technology](https://status.polygon.technology).
3. Se RPC público fora, usar RPC privado (Alchemy/Infura/QuickNode).

**Mitigação estrutural:** em produção, rodar 2+ RPCs em rotação. Atualmente `POLYGON_RPC_URL` só aceita 1 — expansão pendente.

### 5.3 Anchor em `failed` por 48 h

**Investigação:**
1. `SELECT * FROM blockchain_anchors WHERE id = <X>`
2. Verificar `merkle_root` e `transaction_id` nos explorers:
   - Polygon: `https://amoy.polygonscan.com/tx/<transaction_id>`
   - Bitcoin OTS: inspecionar arquivo `.ots` em `proof_uri` com `ots info <file>`
3. Se a tx existe mas não foi confirmada (gas price baixo demais), re-submit manual:
   ```python
   from src.services.anchoring_service import submit_anchor
   new_receipt = submit_anchor(root, "polygon", provider="polygon", ...)
   # update do row existente com novo transaction_id + status='pending'
   ```
4. Se tx não existe (carteira sem fundos, nonce conflict), reabastecer wallet + re-submit.

### 5.4 Wallet comprometida

**Escopo do dano:** apenas ancoragens futuras podem ser falsificadas. Anchors já `confirmed` em bloco Polygon permanecem íntegros (a raiz Merkle está imutável on-chain).

**Procedimento:**
1. Rotacionar `POLYGON_DEPLOYER_PRIVATE_KEY`.
2. Redeployar o contrato `SandboxAnchor` (novo endereço) OU continuar usando o mesmo contrato — qualquer wallet pode submeter; o `msg.sender` fica registrado no evento `Anchored`. Para reforçar após incidente, recomenda-se redeployar com nova wallet + mapping `tenant_id → submitter autorizado` (requer nova major version do contrato).
3. Atualizar `POLYGON_SANDBOX_ANCHOR_ADDRESS` no env.
4. Auditoria: listar eventos `Anchored` com `submitter == wallet comprometida` e sinalizar para revisão.

---

## 6. Métricas e alertas recomendados

| Métrica | Threshold | Ação |
|---|---|---|
| Anchors `pending` > 1 h (Polygon) | > 10 | alerta warning |
| Anchors `failed` no último dia | > 0 | alerta crítico |
| Taxa de `confirmed` sobre `submitted` | < 98% em 24 h | revisar provider/RPC |
| Gas estimado de ancoragem | > 5× média 7d | investigar spam Polygon |
| Idade do anchor `global` mais recente | > 26 h | cron de ancoragem falhou |

Expor via `/api/v1/health` ou Prometheus exporter quando plataforma de observabilidade estiver formalizada (fora do escopo SCC).

---

## 7. Auditoria externa

Terceiros (ANVISA, auditor, imprensa) verificam uma ancoragem via:

```
GET /api/v1/public/anchors/<tenant_id>/verify
    ?table=<event_table>
    &event_id=<id>
```

Resposta inclui `merkle_path`, `merkle_root`, `transaction_id` e `server_verified` (ver [public_anchors.py](../src/web/routes/public_anchors.py)). A verificação independente cruza com:

1. O evento `Anchored` emitido pelo contrato `SandboxAnchor` no `transaction_id`.
2. Recomputação local do `merkle_root` a partir do `event_hash` + `merkle_path`.
3. (Para OTS) Inspeção do arquivo `.ots` em `proof_uri` com `ots verify`.

Os 3 caminhos devem convergir no mesmo `merkle_root` — divergência = corrupção da plataforma.

---

## 8. Pendências registradas

- **Plugar** `_ProductionPolygonClient.anchor()` para assinar transação real com web3.py após o deploy.
- **Plugar** `_ProductionOtsClient.stamp()` usando `opentimestamps-client` (DetachedTimestampFile + RemoteCalendar).
- **Criar** `scripts/anchor_upgrade_cron.py` e plugar no cron de produção.
- **Multi-sig** para a wallet de deploy em mainnet.
- **Verificação do bytecode** no Polygonscan após deploy.
- **Dashboard Grafana** com as métricas de §6.

Registradas neste runbook para seguir visíveis até serem fechadas.
