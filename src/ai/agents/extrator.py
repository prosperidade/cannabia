# src/ai/agents/extrator.py
"""
Agente Extrator — busca, classifica e ingere documentos na base de conhecimento.

Capabilities:
1. Automatic web search (PubMed, ANVISA, Google Scholar, Planalto)
2. Document classification (legislation vs scientific vs guideline)
3. Smart routing (ChromaDB for articles, Google Files API for legislation)
4. Metadata extraction (title, authors, DOI, norm number)
5. Unified catalog registration in PostgreSQL
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

from src.ai.agents.base import BaseAgent, AgentResult

logger = logging.getLogger("cannabia.agents.extrator")

# PubMed E-utilities base URL (free, no API key required for low volume)
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_EMAIL = os.getenv("PUBMED_EMAIL", "cannabia@system.local")

# Default search terms for cannabis medicinal
DEFAULT_CANNABIS_TERMS = [
    "cannabidiol therapeutic",
    "CBD chronic pain systematic review",
    "THC epilepsy clinical trial",
    "cannabis medicinal anxiety",
    "cannabinoid dosage safety",
    "CBD sleep disorder",
    "medical cannabis pharmacokinetics",
]

LEGISLATION_URLS = {
    "RDC 327/2019": "https://www.in.gov.br/web/dou/-/resolucao-da-diretoria-colegiada-rdc-n-327-de-9-de-dezembro-de-2019-232669072",
    "RDC 660/2022": "https://www.in.gov.br/web/dou/-/resolucao-rdc-n-660-de-30-de-marco-de-2022-389908959",
    "Lei 11.343/2006": "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm",
}


class AgenteExtrator(BaseAgent):
    palace_room = "pipeline_cientifico"
    agent_name = "extrator"
    description = "Busca, classifica e ingere documentos na base de conhecimento (PubMed, ANVISA, Scholar)"

    def _register_skills(self):
        self.register_skill(
            "search_pubmed",
            self._search_pubmed,
            "Busca artigos no PubMed por termo de pesquisa",
        )
        self.register_skill(
            "fetch_pubmed_article",
            self._fetch_pubmed_article,
            "Busca metadados completos de um artigo PubMed por PMID",
        )
        self.register_skill(
            "search_legislation",
            self._search_legislation,
            "Busca legislacao em fontes oficiais (ANVISA, Planalto)",
        )
        self.register_skill(
            "classify_document",
            self._classify_document,
            "Classifica documento como artigo, legislacao, guideline ou protocolo",
        )
        self.register_skill(
            "ingest_to_chromadb",
            self._ingest_to_chromadb,
            "Ingere documento como chunks no ChromaDB",
        )
        self.register_skill(
            "ingest_to_google_files",
            self._ingest_to_google_files,
            "Envia documento para Google Files API",
        )
        self.register_skill(
            "register_in_catalog",
            self._register_in_catalog,
            "Registra documento no catalogo unificado (PostgreSQL)",
        )
        self.register_skill(
            "auto_search_and_ingest",
            self._auto_search_and_ingest,
            "Busca automatica na internet e ingere resultados",
        )
        self.register_skill(
            "check_monitor",
            self._check_monitor,
            "Verifica uma fonte monitorada por novidades",
        )
        self.register_skill(
            "run_all_monitors",
            self._run_all_monitors,
            "Executa todos os monitores ativos que estão no horário de verificação",
        )

    # ── Helpers ──

    @staticmethod
    def _parse_pubmed_date(raw: str) -> Optional[str]:
        """Parse PubMed date formats ('2021 Mar', '2021 Mar 15', '2021') to ISO date."""
        if not raw:
            return None
        import calendar
        parts = raw.split()
        try:
            year = int(parts[0])
            month = 1
            day = 1
            if len(parts) >= 2:
                # Try month abbreviation
                for i, abbr in enumerate(calendar.month_abbr):
                    if abbr and parts[1].startswith(abbr):
                        month = i
                        break
            if len(parts) >= 3:
                day = int(parts[2])
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            return None

    # ── PubMed Search ──

    def _search_pubmed(self, query: str, max_results: int = 10, **kwargs) -> dict:
        """Search PubMed for articles matching query."""
        import requests

        try:
            # Step 1: ESearch - get PMIDs
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

            pmids = data.get("esearchresult", {}).get("idlist", [])
            total_found = int(data.get("esearchresult", {}).get("count", 0))

            if not pmids:
                return {"articles": [], "total_found": total_found, "query": query}

            # Step 2: ESummary - get article metadata
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

            articles = []
            results = summary_data.get("result", {})
            for pmid in pmids:
                article = results.get(pmid, {})
                if not isinstance(article, dict):
                    continue

                authors = []
                for author in article.get("authors", []):
                    if isinstance(author, dict):
                        authors.append(author.get("name", ""))

                articles.append({
                    "pmid": pmid,
                    "title": article.get("title", ""),
                    "authors": authors,
                    "journal": article.get("fulljournalname", article.get("source", "")),
                    "published_date": self._parse_pubmed_date(article.get("pubdate", "")),
                    "doi": next(
                        (aid.get("value", "") for aid in article.get("articleids", [])
                         if isinstance(aid, dict) and aid.get("idtype") == "doi"),
                        "",
                    ),
                    "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })

            logger.info("PubMed search '%s': %d results (of %d total)", query, len(articles), total_found)
            return {"articles": articles, "total_found": total_found, "query": query}

        except Exception as e:
            logger.warning("PubMed search failed: %s", e)
            return {"articles": [], "total_found": 0, "query": query, "error": str(e)}

    def _fetch_pubmed_article(self, pmid: str, **kwargs) -> dict:
        """Fetch full abstract for a PubMed article."""
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
            abstract_text = resp.text.strip()

            return {"pmid": pmid, "abstract": abstract_text, "success": True}
        except Exception as e:
            return {"pmid": pmid, "abstract": "", "success": False, "error": str(e)}

    # ── Legislation Search ──

    def _search_legislation(self, query: str = "", **kwargs) -> dict:
        """Search known legislation sources for cannabis-related norms."""
        results = []

        # Known legislation URLs
        for norm_name, url in LEGISLATION_URLS.items():
            if not query or query.lower() in norm_name.lower():
                results.append({
                    "norm_number": norm_name,
                    "source_url": url,
                    "source": "planalto" if "planalto" in url else "anvisa",
                    "doc_type": "legislation",
                    "status": "known",
                })

        # Try ANVISA search
        if query:
            try:
                import requests
                anvisa_url = "https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cannabis"
                resp = requests.get(anvisa_url, timeout=10)
                if resp.ok:
                    results.append({
                        "norm_number": "",
                        "source_url": anvisa_url,
                        "source": "anvisa",
                        "doc_type": "legislation",
                        "status": "portal_available",
                        "note": "Portal ANVISA Cannabis disponivel para consulta manual",
                    })
            except Exception:
                pass

        return {"results": results, "query": query}

    # ── Document Classification ──

    def _classify_document(self, title: str = "", content: str = "", filename: str = "", **kwargs) -> dict:
        """Classify a document by type and determine optimal storage."""
        text = f"{title} {content} {filename}".lower()

        # Legislation patterns
        leg_patterns = [
            r"rdc\s*\d+", r"resoluc[aã]o", r"portaria", r"lei\s*\d+",
            r"decreto", r"instruc[aã]o\s*normativa", r"anvisa", r"cfm",
            r"conama", r"diario\s*oficial",
        ]
        is_legislation = any(re.search(p, text) for p in leg_patterns)

        # Scientific article patterns
        sci_patterns = [
            r"abstract", r"doi:", r"pubmed", r"clinical\s*trial",
            r"systematic\s*review", r"meta.analysis", r"randomized",
            r"placebo", r"double.blind", r"cohort", r"p\s*[<>=]\s*0\.\d+",
        ]
        is_scientific = any(re.search(p, text) for p in sci_patterns)

        # Guideline patterns
        guide_patterns = [
            r"guideline", r"protocolo", r"consenso", r"recomenda[cç][aã]o",
            r"diretriz", r"manual\s*(de|do|da)",
        ]
        is_guideline = any(re.search(p, text) for p in guide_patterns)

        # Determine type and storage
        if is_legislation:
            doc_type = "legislation"
            storage_type = "google_files"  # Full context needed
            reason = "Legislacao precisa de contexto completo para referencias cruzadas entre artigos"
        elif is_scientific:
            doc_type = "article"
            storage_type = "chromadb"  # Chunks work well for articles
            reason = "Artigos cientificos sao autocontidos por secao — chunks funcionam bem"
        elif is_guideline:
            doc_type = "guideline"
            storage_type = "google_files"  # Guidelines need full context too
            reason = "Guidelines sao sequenciais e precisam de contexto completo"
        else:
            doc_type = "unknown"
            storage_type = "chromadb"  # Default to chunks
            reason = "Tipo nao identificado — usando chunks como padrao"

        return {
            "doc_type": doc_type,
            "storage_type": storage_type,
            "reason": reason,
            "is_legislation": is_legislation,
            "is_scientific": is_scientific,
            "is_guideline": is_guideline,
        }

    # ── Ingestion ──

    def _ingest_to_chromadb(self, text: str, metadata: dict, chunk_size: int = 1000, **kwargs) -> dict:
        """Split text into chunks and ingest into ChromaDB."""
        try:
            from src.knowledge.embeddings import EmbeddingClient
            from src.knowledge.vector_store import KnowledgeStore

            embedder = EmbeddingClient()
            store = KnowledgeStore()

            # Simple chunking by paragraphs/size
            paragraphs = text.split("\n\n")
            chunks = []
            current_chunk = ""

            for para in paragraphs:
                if len(current_chunk) + len(para) > chunk_size:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = para
                else:
                    current_chunk += "\n\n" + para

            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            # Embed and store each chunk
            doc_id = metadata.get("id", str(hash(text[:100])))
            stored = 0
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                try:
                    embedding = embedder.embed_document(chunk)
                    store.add(
                        chunk_id=chunk_id,
                        embedding=embedding,
                        text=chunk,
                        metadata={**metadata, "chunk_index": i, "total_chunks": len(chunks)},
                    )
                    stored += 1
                except Exception:
                    logger.warning("Failed to store chunk %d", i)

            return {"chunks_total": len(chunks), "chunks_stored": stored, "success": stored > 0}

        except Exception as e:
            logger.error("ChromaDB ingestion failed: %s", e)
            return {"chunks_total": 0, "chunks_stored": 0, "success": False, "error": str(e)}

    def _ingest_to_google_files(self, filepath: str, display_name: str = "", **kwargs) -> dict:
        """Upload document to Google Files API."""
        try:
            from src.knowledge.google_files import upload_file
            result = upload_file(filepath, display_name or None)
            return {
                "uri": result.get("uri", ""),
                "name": result.get("name", ""),
                "success": True,
            }
        except Exception as e:
            logger.error("Google Files upload failed: %s", e)
            return {"uri": "", "name": "", "success": False, "error": str(e)}

    # ── Catalog Registration ──

    def _register_in_catalog(self, doc_data: dict, **kwargs) -> dict:
        """Register document in the PostgreSQL knowledge_catalog table.

        Delegates to src.knowledge.auto_ingest.register_article_in_catalog
        (single source of truth — also used by BaseAgent.register_to_knowledge_base
        when other agents ingest material during attendance).
        """
        from src.knowledge.auto_ingest import register_article_in_catalog
        return register_article_in_catalog(doc_data)

    # ── Auto Search & Ingest ──

    def _auto_search_and_ingest(self, terms: list = None, max_per_term: int = 5, **kwargs) -> dict:
        """Automatically search PubMed for cannabis articles and register in catalog."""
        search_terms = terms or DEFAULT_CANNABIS_TERMS
        created_by = kwargs.get("created_by")
        total_found = 0
        total_registered = 0
        results_detail = []

        for term in search_terms:
            pubmed_result = self._search_pubmed(query=term, max_results=max_per_term)
            articles = pubmed_result.get("articles", [])
            total_found += len(articles)

            for article in articles:
                # Fetch abstract
                abstract_result = self._fetch_pubmed_article(pmid=article["pmid"])

                # Classify
                classification = self._classify_document(
                    title=article.get("title", ""),
                    content=abstract_result.get("abstract", ""),
                )

                # Register in catalog
                doc_data = {
                    "title": article.get("title", ""),
                    "doc_type": classification["doc_type"],
                    "source": "pubmed",
                    "source_url": article.get("source_url", ""),
                    "doi": article.get("doi", ""),
                    "category": "cannabis_medicinal",
                    "tags": [term],
                    "authors": article.get("authors", []),
                    "journal": article.get("journal", ""),
                    "published_date": article.get("published_date"),
                    "language": "en",
                    "abstract": abstract_result.get("abstract", ""),
                    "storage_type": classification["storage_type"],
                    "status": "indexed",
                    "ingested_by": "agent_extrator_auto",
                    "created_by": created_by,
                }

                reg = self._register_in_catalog(doc_data=doc_data)
                if reg.get("registered"):
                    total_registered += 1
                    results_detail.append({
                        "title": article["title"][:80],
                        "doi": article.get("doi", ""),
                        "catalog_id": reg["catalog_id"],
                    })

                # Rate limit (PubMed asks for 3 req/s max)
                time.sleep(0.4)

        # Also register known legislation
        leg_result = self._search_legislation()
        for leg in leg_result.get("results", []):
            if leg.get("norm_number"):
                doc_data = {
                    "title": leg["norm_number"],
                    "doc_type": "legislation",
                    "source": leg.get("source", "anvisa"),
                    "source_url": leg.get("source_url", ""),
                    "norm_number": leg["norm_number"],
                    "norm_body": leg.get("source", "").upper(),
                    "norm_status": "vigente",
                    "storage_type": "google_files",
                    "status": "pending",  # Needs manual PDF upload
                    "ingested_by": "agent_extrator_auto",
                    "category": "legislacao_cannabis",
                    "created_by": created_by,
                }
                reg = self._register_in_catalog(doc_data=doc_data)
                if reg.get("registered"):
                    total_registered += 1

        return {
            "terms_searched": len(search_terms),
            "total_found": total_found,
            "total_registered": total_registered,
            "details": results_detail,
        }

    # ── Web Monitoring ──

    def _check_monitor(self, monitor: dict, **kwargs) -> dict:
        """Check a single monitored source for new content."""
        import requests
        import hashlib

        source_type = monitor.get("source_type", "")
        url = monitor.get("url", "")
        search_query = monitor.get("search_query", "")
        max_items = monitor.get("max_items", 10)
        last_hash = monitor.get("last_hash", "")

        new_items = []
        current_hash = ""

        try:
            if source_type == "pubmed_query" and search_query:
                # Use existing PubMed search
                result = self._search_pubmed(query=search_query, max_results=max_items)
                articles = result.get("articles", [])

                # Hash current results to detect changes
                content_str = json.dumps([a.get("pmid") for a in articles])
                current_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

                if current_hash != last_hash:
                    # New content detected — register new articles
                    for article in articles:
                        abstract_result = self._fetch_pubmed_article(pmid=article["pmid"])
                        classification = self._classify_document(
                            title=article.get("title", ""),
                            content=abstract_result.get("abstract", ""),
                        )
                        doc_data = {
                            "title": article.get("title", ""),
                            "doc_type": classification["doc_type"],
                            "source": "pubmed",
                            "source_url": article.get("source_url", ""),
                            "doi": article.get("doi", ""),
                            "category": "cannabis_medicinal",
                            "tags": [search_query.split()[0] if search_query else "cannabis"],
                            "authors": article.get("authors", []),
                            "journal": article.get("journal", ""),
                            "published_date": article.get("published_date"),
                            "language": "en",
                            "abstract": abstract_result.get("abstract", ""),
                            "storage_type": classification["storage_type"],
                            "status": "indexed",
                            "ingested_by": "monitor_auto",
                        }
                        reg = self._register_in_catalog(doc_data=doc_data)
                        if reg.get("registered"):
                            new_items.append({"title": article["title"][:80], "catalog_id": reg["catalog_id"]})
                        time.sleep(0.4)  # PubMed rate limit

            elif source_type == "html_page":
                # Fetch page and check for changes
                resp = requests.get(url, timeout=15, headers={"User-Agent": "CannabIA-KnowledgeBot/1.0"})
                if resp.ok:
                    current_hash = hashlib.sha256(resp.content).hexdigest()[:16]
                    if current_hash != last_hash and last_hash:
                        new_items.append({
                            "title": f"Conteudo atualizado: {monitor.get('name', url)}",
                            "url": url,
                            "change_detected": True,
                        })

        except Exception as e:
            logger.warning("Monitor check failed for '%s': %s", monitor.get("name"), e)
            return {"checked": False, "error": str(e), "new_items": [], "hash": current_hash}

        return {
            "checked": True,
            "new_items": new_items,
            "items_count": len(new_items),
            "hash": current_hash,
            "changed": current_hash != last_hash,
        }

    def _run_all_monitors(self, **kwargs) -> dict:
        """Run all active monitors that are due for checking."""
        from src.infra.database import db_cursor

        results = []
        total_new = 0

        try:
            with db_cursor(dictionary=True) as (conn, cursor):
                # Get active monitors due for checking
                cursor.execute(
                    """
                    SELECT * FROM knowledge_monitors
                    WHERE is_active = TRUE
                      AND (last_checked_at IS NULL
                           OR last_checked_at < NOW() - (check_interval_hours || ' hours')::interval)
                    ORDER BY last_checked_at ASC NULLS FIRST
                    """,
                )
                monitors = cursor.fetchall()

                if not monitors:
                    return {"monitors_checked": 0, "total_new_items": 0, "message": "Nenhum monitor pendente"}

                for monitor in monitors:
                    logger.info("Checking monitor: %s", monitor["name"])
                    check_result = self._check_monitor(monitor=monitor)

                    # Update monitor state
                    cursor.execute(
                        """
                        UPDATE knowledge_monitors
                        SET last_checked_at = NOW(),
                            last_hash = %s,
                            items_found = items_found + %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            check_result.get("hash", ""),
                            check_result.get("items_count", 0),
                            monitor["id"],
                        ),
                    )

                    new_count = check_result.get("items_count", 0)
                    total_new += new_count
                    results.append({
                        "monitor": monitor["name"],
                        "source_type": monitor["source_type"],
                        "checked": check_result.get("checked", False),
                        "new_items": new_count,
                        "changed": check_result.get("changed", False),
                    })

                conn.commit()

        except Exception as e:
            logger.error("Monitor run failed: %s", e)
            return {"monitors_checked": 0, "total_new_items": 0, "error": str(e)}

        return {
            "monitors_checked": len(results),
            "total_new_items": total_new,
            "results": results,
        }

    # ── Main Execute ──

    def execute(self, **kwargs) -> AgentResult:
        action = kwargs.get("action", "auto_search")

        if action == "auto_search":
            terms = kwargs.get("terms")
            max_per_term = kwargs.get("max_per_term", 5)
            created_by = kwargs.get("created_by")
            result = self.invoke_skill(
                "auto_search_and_ingest",
                terms=terms,
                max_per_term=max_per_term,
                created_by=created_by,
            )

            self.remember(
                f"Auto-search completed: {result['total_registered']} new documents "
                f"from {result['terms_searched']} search terms"
            )

            return AgentResult(
                success=True,
                data=result,
                confidence=0.8,
                skills_used=["search_pubmed", "fetch_pubmed_article", "classify_document", "register_in_catalog", "search_legislation"],
            )

        elif action == "classify":
            classification = self.invoke_skill(
                "classify_document",
                title=kwargs.get("title", ""),
                content=kwargs.get("content", ""),
                filename=kwargs.get("filename", ""),
            )
            return AgentResult(success=True, data=classification, confidence=0.85, skills_used=["classify_document"])

        elif action == "ingest_file":
            filepath = kwargs.get("filepath", "")
            title = kwargs.get("title", "")
            if not filepath:
                return AgentResult(success=False, error="filepath is required")

            # Classify
            classification = self.invoke_skill("classify_document", title=title, filename=filepath)

            if classification["storage_type"] == "google_files":
                ingest_result = self.invoke_skill("ingest_to_google_files", filepath=filepath, display_name=title)
                skills = ["classify_document", "ingest_to_google_files"]
            else:
                # Read file content for ChromaDB
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    content = ""
                ingest_result = self.invoke_skill(
                    "ingest_to_chromadb",
                    text=content,
                    metadata={"title": title, "source": "manual_upload"},
                )
                skills = ["classify_document", "ingest_to_chromadb"]

            return AgentResult(
                success=ingest_result.get("success", False),
                data={**classification, **ingest_result},
                confidence=0.8,
                skills_used=skills,
            )

        elif action == "search_pubmed":
            query = kwargs.get("query", "cannabidiol")
            result = self.invoke_skill("search_pubmed", query=query, max_results=kwargs.get("max_results", 10))
            return AgentResult(success=True, data=result, skills_used=["search_pubmed"])

        elif action == "search_legislation":
            result = self.invoke_skill("search_legislation", query=kwargs.get("query", ""))
            return AgentResult(success=True, data=result, skills_used=["search_legislation"])

        elif action == "run_monitors":
            result = self.invoke_skill("run_all_monitors")
            self.remember(f"Monitors checked: {result.get('monitors_checked', 0)}, new items: {result.get('total_new_items', 0)}")
            return AgentResult(
                success=True,
                data=result,
                confidence=0.9,
                skills_used=["run_all_monitors", "check_monitor"],
            )

        else:
            return AgentResult(success=False, error=f"Unknown action: {action}")
