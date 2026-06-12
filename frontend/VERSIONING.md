# Política de Versionamento — Frontend Cannab'IA

> Origem: doc 29.7 (Mergulho Frontend) R8/R9 e doc 30 (Remediação) FE-2.
> Objetivo: builds reproduzíveis sem travar a manutenção de dependências.

## Regras

1. **Caret (`^`) como padrão.** Dependências e devDependencies usam faixa
   caret (ex.: `^3.5.3`). Isso permite absorver patches e minors de bugfix
   sem editar `package.json` a cada atualização.

2. **`package-lock.json` é a fonte da verdade.** O lockfile (lockfileVersion 3) fixa a árvore exata resolvida. É versionado e **nunca** deve ser
   ignorado. Mudanças de dependência sempre acompanham o lock atualizado no
   mesmo commit.

3. **`npm ci` obrigatório em CI e deploy.** Nunca `npm install` em ambiente
   automatizado. `npm ci` instala estritamente o que está no lockfile e
   **falha** se `package.json` e `package-lock.json` divergirem — é o gate
   que garante reprodutibilidade (Render usa o mesmo comando no build).

4. **Pin exato para o trio que mais quebra em minor:** `next`, `react` e
   `react-dom` ficam **sem caret** (ex.: `next: "16.2.2"`). São o núcleo de
   renderização; um minor inesperado deles é a causa mais comum de quebra
   silenciosa de build/runtime. A subida desse trio é sempre deliberada:
   editar `package.json` → `npm install` → revisar o diff do lock → CI verde.

5. **Atualização de dependências por janela mensal.** Renovate ou Dependabot
   abre PRs agrupados uma vez por mês. Critério de merge: **Frontend CI
   verde** (lint · format:check · tsc · build). Sem CI verde, não entra.

## Como subir o trio next/react/react-dom (procedimento deliberado)

```bash
cd frontend
# editar package.json com a versão exata desejada (sem ^)
npm install            # sincroniza package-lock.json
git add package.json package-lock.json
# abrir PR — Frontend CI precisa ficar verde antes do merge
```

## Gate de CI

`.github/workflows/frontend-ci.yml` roda em todo PR/push que toca
`frontend/**`:

```
npm ci → npm run lint → npm run format:check → npx tsc --noEmit → npm run build
```

Qualquer passo vermelho bloqueia o merge.
