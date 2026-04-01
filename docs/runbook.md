# Runbook de Trabalho

## Início de vigência

2026-04-01

## Propósito

Este runbook define o padrão operacional mínimo de documentação contínua da CannabIA a partir de 2026-04-01.

O objetivo é manter um histórico simples, cumulativo e rastreável de:

- decisões
- progresso diário
- bloqueios
- próximos passos
- arquivos impactados

## Regra principal

Todo dia de trabalho deve gerar um novo arquivo de progresso na pasta `docs`, seguindo a sequência:

```text
progresso1.md
progresso2.md
progresso3.md
...
```

## Convenção obrigatória

- Cada arquivo `progressoN.md` representa um dia ou ciclo diário de trabalho
- A data deve ser registrada explicitamente dentro do arquivo
- Se houver mais de uma sessão no mesmo dia, o conteúdo deve ser acrescentado no mesmo arquivo do dia
- O próximo arquivo só deve ser aberto quando houver um novo dia de trabalho
- O conteúdo deve ser objetivo, rastreável e técnico

## Estrutura mínima de cada progresso diário

Cada arquivo `progressoN.md` deve conter, no mínimo:

```text
# Progresso N

## Data
## Objetivo do dia
## Trabalho realizado
## Decisões registradas
## Próximos passos
## Arquivos relevantes do dia
## Bloqueios
```

## Regras de preenchimento

- Registrar o que realmente foi feito, sem texto genérico
- Listar decisões que afetam arquitetura, backlog, fluxo ou operação
- Informar bloqueios reais, se existirem
- Encerrar o arquivo com próximos passos claros
- Sempre citar arquivos importantes tocados ou criados no dia

## Quando atualizar o runbook

O `runbook.md` deve ser atualizado quando houver mudança em:

- convenção de nome dos arquivos diários
- estrutura mínima dos registros
- padrão de documentação do time
- regras de operação e handoff

## Padrão adotado a partir de hoje

Em 2026-04-01, fica definido que:

- a pasta oficial desses registros é `docs`
- o primeiro arquivo da sequência é `docs/progresso1.md`
- este `docs/runbook.md` passa a ser a referência operacional do padrão

## Observação final

Este runbook é um documento vivo. Ele deve permanecer curto, prático e útil para a execução diária.
