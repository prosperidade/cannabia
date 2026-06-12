import { useEffect, useState, type DependencyList } from "react";

export interface FetchState<T> {
  /** Dados da requisição mais recente já liquidada; `null` enquanto carrega ou em erro. */
  data: T | null;
  /** `true` até a requisição da época atual liquidar (sucesso ou erro). */
  loading: boolean;
  /** Mensagem de erro da requisição atual, ou `null`. */
  error: string | null;
}

/**
 * Busca de dados assíncrona no mount (e quando `deps` mudam), SEM `setState`
 * síncrono dentro do effect — o `loading` é **derivado** do ciclo da
 * requisição, e não setado no corpo do effect. Isso cumpre a regra
 * `react-hooks/set-state-in-effect` (React Compiler / next 16) que sinaliza
 * o idioma `setLoading(true)` no topo do effect como causa de render extra.
 *
 * Padrão único de data-fetching do frontend: páginas novas devem usar este
 * hook em vez de reescrever o `useEffect + setLoading` à mão (senão a dívida
 * `set-state-in-effect` renasce). Cancela updates de respostas obsoletas
 * (corrida) comparando a "época" da requisição com as `deps` atuais.
 *
 * `fetcher` e `errorFallback` ficam fora das deps de propósito: o ciclo é
 * controlado pelas `deps` do chamador, como num `useEffect` de fetch.
 *
 * @example
 *   const { data, loading } = useFetchData(() => getAdminStats(), []);
 */
export function useFetchData<T>(
  fetcher: () => Promise<T>,
  deps: DependencyList = [],
  errorFallback = "Falha ao carregar dados.",
): FetchState<T> {
  // Época da requisição corrente = identidade das deps. Ao mudar, o resultado
  // anterior fica obsoleto e voltamos a `loading`.
  const epoch = JSON.stringify(deps);
  const [settled, setSettled] = useState<{
    epoch: string;
    data: T | null;
    error: string | null;
  }>({ epoch: "", data: null, error: null });

  useEffect(() => {
    let alive = true;
    fetcher()
      .then((data) => {
        if (alive) setSettled({ epoch, data, error: null });
      })
      .catch((err) => {
        if (alive) {
          setSettled({
            epoch,
            data: null,
            error: err instanceof Error ? err.message : errorFallback,
          });
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // `loading` derivado: enquanto o resultado liquidado não for da época atual,
  // ainda estamos carregando. Nenhum setState síncrono no effect.
  const loading = settled.epoch !== epoch;
  return {
    data: loading ? null : settled.data,
    loading,
    error: loading ? null : settled.error,
  };
}
