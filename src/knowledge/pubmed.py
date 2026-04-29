# src/knowledge/pubmed.py
"""
Cliente PubMed standalone via E-utilities.

Extraido para que multiplos agentes (Extrator no fluxo manual, Cientifico
no gancho durante atendimento) possam buscar PubMed sem dependencia
cruzada entre agentes.

E-utilities sao gratuitas e nao exigem chave API para volume baixo
(<3 req/s). PUBMED_EMAIL identifica o cliente para a NCBI.
"""

from __future__ import annotations

import calendar
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cannabia.knowledge.pubmed")

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_EMAIL = os.getenv("PUBMED_EMAIL", "cannabia@system.local")


def parse_pubmed_date(raw: str) -> Optional[str]:
    """Normaliza datas PubMed ('2021 Mar', '2021 Mar 15', '2021') para ISO."""
    if not raw:
        return None
    parts = raw.split()
    try:
        year = int(parts[0])
        month = 1
        day = 1
        if len(parts) >= 2:
            for i, abbr in enumerate(calendar.month_abbr):
                if abbr and parts[1].startswith(abbr):
                    month = i
                    break
        if len(parts) >= 3:
            day = int(parts[2])
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, IndexError):
        return None


def search_pubmed_articles(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Busca PubMed e retorna metadados (titulo, autores, journal, DOI, URL).

    Retorna:
      {"articles": [...], "total_found": int, "query": str, "error"?: str}

    Cada article tem: pmid, title, authors, journal, published_date, doi, source_url.
    """
    import requests

    try:
        search_url = f"{PUBMED_BASE}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
            "email": PUBMED_EMAIL,
        }
        resp = requests.get(search_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        pmids: List[str] = data.get("esearchresult", {}).get("idlist", [])
        total_found = int(data.get("esearchresult", {}).get("count", 0))

        if not pmids:
            return {"articles": [], "total_found": total_found, "query": query}

        summary_url = f"{PUBMED_BASE}/esummary.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "email": PUBMED_EMAIL,
        }
        resp = requests.get(summary_url, params=params, timeout=15)
        resp.raise_for_status()
        summary_data = resp.json()

        articles: List[Dict[str, Any]] = []
        results = summary_data.get("result", {})
        for pmid in pmids:
            article = results.get(pmid, {})
            if not isinstance(article, dict):
                continue

            authors: List[str] = []
            for author in article.get("authors", []):
                if isinstance(author, dict):
                    authors.append(author.get("name", ""))

            doi = next(
                (
                    aid.get("value", "")
                    for aid in article.get("articleids", [])
                    if isinstance(aid, dict) and aid.get("idtype") == "doi"
                ),
                "",
            )

            articles.append(
                {
                    "pmid": pmid,
                    "title": article.get("title", ""),
                    "authors": authors,
                    "journal": article.get("fulljournalname", article.get("source", "")),
                    "published_date": parse_pubmed_date(article.get("pubdate", "")),
                    "doi": doi,
                    "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
            )

        logger.info("PubMed search '%s': %d results (of %d total)", query, len(articles), total_found)
        return {"articles": articles, "total_found": total_found, "query": query}

    except Exception as e:
        logger.warning("PubMed search failed: %s", e)
        return {"articles": [], "total_found": 0, "query": query, "error": str(e)}


def fetch_pubmed_abstract(pmid: str) -> Dict[str, Any]:
    """Busca o abstract completo de um artigo PubMed por PMID."""
    import requests

    try:
        url = f"{PUBMED_BASE}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "rettype": "abstract",
            "retmode": "text",
            "email": PUBMED_EMAIL,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return {"pmid": pmid, "abstract": resp.text.strip(), "success": True}
    except Exception as e:
        return {"pmid": pmid, "abstract": "", "success": False, "error": str(e)}
