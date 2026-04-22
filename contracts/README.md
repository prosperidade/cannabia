# Smart Contracts — Sandbox Compliance Core (SCC)

Contratos Solidity para ancoragem de Merkle roots em blockchain pública.
Referência de domínio: [docs/26_BLOCKCHAIN_ANCHORING_PROTOCOL.md](../docs/26_BLOCKCHAIN_ANCHORING_PROTOCOL.md).

## SandboxAnchor.sol

Registro append-only de `(scope, scopeId, merkleRoot, periodStart, periodEnd)`. Cada chamada emite o evento `Anchored` — filtrável por anchorId, scopeId ou merkleRoot.

### Compilação

Qualquer toolchain Solidity 0.8.20+ serve. Exemplos:

**Hardhat:**
```bash
npm install --save-dev hardhat @nomicfoundation/hardhat-toolbox
npx hardhat compile
```

**Foundry:**
```bash
forge build
```

### Deploy — Polygon Amoy (testnet)

Decisão de rede: **Polygon Amoy** para homologação, promoção para mainnet após validação formal com ANVISA + consultoria jurídica (doc 26 §5.3).

Variáveis de ambiente esperadas:

```env
POLYGON_RPC_URL=https://rpc-amoy.polygon.technology
POLYGON_DEPLOYER_PRIVATE_KEY=0x...         # wallet com saldo em MATIC de testnet
POLYGON_SANDBOX_ANCHOR_ADDRESS=<populado apos deploy>
```

Após deploy, exporte o endereço do contrato via env var `POLYGON_SANDBOX_ANCHOR_ADDRESS` e habilite o provider polygon no backend:

```env
ANCHORING_PROVIDER=polygon
```

Faucet Amoy: [faucet.polygon.technology](https://faucet.polygon.technology).

### Deploy — Polygon mainnet

Mesmas envs, trocar `POLYGON_RPC_URL` para o endpoint mainnet e a wallet para uma com saldo real. Custo estimado por submissão: centavos a poucos reais (gas Polygon).

### Verificação de código

Após deploy, verificar o bytecode no Polygonscan para tornar público o source-code. Isso é **requisito regulatório** — a ANVISA precisa poder auditar a lógica on-chain.

## Testes do contrato

Os testes Python em [tests/test_polygon_anchor.py](../tests/test_polygon_anchor.py) usam client injetado (fake web3) e cobrem o wrapper [src/integrations/polygon_anchor.py](../src/integrations/polygon_anchor.py). Para testar o contrato em si (reverts, events), use Hardhat/Foundry com a suite em `contracts/test/` — pendência registrada em F5.7 (runbook).

## Segurança

- O contrato **não tem owner nem função admin** — qualquer wallet pode submeter ancoragens. Controle de acesso é off-chain (CannabIA valida tenant/role antes de assinar a transação).
- Nenhum caminho de UPDATE/DELETE — append-only é propriedade estrutural.
- Wallet de deploy deve ser **multi-sig** em produção (pendência F5.7).
