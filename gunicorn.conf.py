# gunicorn.conf.py
"""
Configuração centralizada do Gunicorn para deploy multi-worker.

Variáveis de ambiente:
  WEB_CONCURRENCY     — número de workers (padrão: 2)
  GUNICORN_WORKER_CLASS — classe do worker (padrão: eventlet)
  GUNICORN_TIMEOUT    — timeout por request em segundos (padrão: 120)
  GUNICORN_KEEPALIVE  — keep-alive em segundos (padrão: 5)
  GUNICORN_MAX_REQUESTS — requests por worker antes de reciclar (padrão: 1000)
  GUNICORN_MAX_REQUESTS_JITTER — jitter para evitar restart simultâneo (padrão: 50)
  GUNICORN_GRACEFUL_TIMEOUT — tempo para graceful shutdown em segundos (padrão: 30)
  PORT                — porta de bind (padrão: 5000)

Uso:
  gunicorn -c gunicorn.conf.py "src.app:app"
"""

import os

# ═══════════════════════════════════════════════════════════════════════════════
# WORKERS
# ═══════════════════════════════════════════════════════════════════════════════

# Número de workers — padrão 2 para starter plan do Render (512MB RAM).
# Fórmula recomendada para eventlet: 2-4 workers (I/O bound, não CPU bound).
# Em planos maiores, escalar para (2 * CPU) + 1.
workers = int(os.getenv("WEB_CONCURRENCY", "2"))

# Classe do worker — eventlet para suporte a SocketIO e I/O assíncrono.
# Alternativa: "gevent" (avaliar na Fase 5 se necessário).
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "eventlet")

# ═══════════════════════════════════════════════════════════════════════════════
# TIMEOUTS E LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════

# Timeout por request — 120s para acomodar pipeline de IA (3 chamadas LLM).
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# Keep-alive — mantém conexão TCP aberta para requests subsequentes.
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Graceful shutdown — tempo para workers finalizarem requests em andamento.
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# ═══════════════════════════════════════════════════════════════════════════════
# RECICLAGEM DE WORKERS (prevenção de memory leaks)
# ═══════════════════════════════════════════════════════════════════════════════

# Recicla worker após N requests (evita memory leaks acumulados).
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))

# Jitter aleatório para evitar que todos os workers reciclem ao mesmo tempo.
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "50"))

# ═══════════════════════════════════════════════════════════════════════════════
# BINDING
# ═══════════════════════════════════════════════════════════════════════════════

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

# Logs para stdout/stderr — compatível com Render, CloudWatch, etc.
accesslog = "-"
errorlog = "-"

# Nível de log do Gunicorn (não afeta logs da aplicação Flask).
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# ═══════════════════════════════════════════════════════════════════════════════
# PRE-FORK HOOK — executa antes de criar cada worker
# ═══════════════════════════════════════════════════════════════════════════════

def pre_fork(server, worker):
    """
    Hook executado no processo master antes de forkar cada worker.
    Útil para fechar conexões que não devem ser compartilhadas entre processos.
    """
    pass


def post_fork(server, worker):
    """
    Hook executado em cada worker após o fork.
    Re-inicializa recursos que não podem ser compartilhados (pools, conexões).
    """
    server.log.info("Worker %s (pid: %s) inicializado.", worker.age, worker.pid)


def worker_exit(server, worker):
    """
    Hook executado quando um worker encerra.
    Libera recursos do worker (conexões de pool, etc).
    """
    server.log.info("Worker %s (pid: %s) encerrado.", worker.age, worker.pid)
