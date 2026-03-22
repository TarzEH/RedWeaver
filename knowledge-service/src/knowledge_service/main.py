"""RedWeaver Knowledge Microservice.

Standalone FastAPI service that indexes security methodology documents into
ChromaDB and exposes a REST API for RAG queries. Runs as an independent
Docker container with the knowledge directory mounted as a read-only volume.

The backend does NOT access knowledge files directly — it queries this service.

Endpoints:
    GET  /health  -> {"status": "ok", "documents_indexed": N, "files_indexed": N}
    POST /query   -> {"status": "success", "query": "...", "results": [...]}
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from fastapi import FastAPI
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("knowledge-service")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KNOWLEDGE_DATA_PATH = os.environ.get("KNOWLEDGE_DATA_PATH", "/data/knowledge")

# Category patterns for precise RAG retrieval
CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("privilege_escalation", ["priv", "escalat", "suid", "sudo", "gtfobins"]),
    ("tunneling", ["tunnel", "ssh", "port forward", "pivot", "sshuttle", "proxychains"]),
    ("flag_hunting", ["flag", "proof.txt", "local.txt"]),
    ("web_attacks", ["web", "sql", "xss", "csrf", "ssrf", "injection", "owasp"]),
    ("active_directory", ["active directory", "ad ", "kerberos", "ldap", "bloodhound"]),
    ("reconnaissance", ["recon", "enum", "info gather", "nmap", "subfinder", "osint"]),
    ("exploitation", ["exploit", "metasploit", "payload", "shellcode", "buffer overflow"]),
    ("password_attacks", ["password", "hash", "crack", "brute", "hydra", "john"]),
    ("reporting", ["report", "template", "documentation"]),
    ("c2_frameworks", ["c2", "command and control", "cobalt", "sliver"]),
    ("av_evasion", ["evasion", "antivirus", "av ", "bypass", "amsi"]),
    ("cloud_security", ["aws", "azure", "cloud", "s3", "iam"]),
]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(description="Search query for the knowledge base")
    category: str | None = Field(default=None, description="Optional category filter")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")


class QueryResult(BaseModel):
    content: str
    file: str
    category: str
    relevance_score: float


class QueryResponse(BaseModel):
    status: str
    query: str
    results_count: int
    results: list[QueryResult]


class HealthResponse(BaseModel):
    status: str
    documents_indexed: int
    files_indexed: int


# ---------------------------------------------------------------------------
# Indexing logic
# ---------------------------------------------------------------------------

def categorize_file(rel_path: str) -> str:
    """Categorize a file based on its path."""
    lower = rel_path.lower()
    for category, patterns in CATEGORY_PATTERNS:
        if any(p in lower for p in patterns):
            return category
    return "general"


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def build_index(data_path: str) -> tuple[Any, int, int]:
    """Discover markdown files, chunk them, and build ChromaDB index."""
    knowledge_path = Path(data_path)
    if not knowledge_path.exists():
        logger.warning("Knowledge data path does not exist: %s", data_path)
        return None, 0, 0

    md_files = sorted(knowledge_path.rglob("*.md"))
    if not md_files:
        logger.warning("No markdown files found in %s", data_path)
        return None, 0, 0

    logger.info("Found %d markdown files in %s", len(md_files), data_path)

    client = chromadb.Client()
    try:
        client.delete_collection("security_knowledge")
    except Exception:
        pass

    collection = client.create_collection(
        name="security_knowledge",
        metadata={"description": "Security methodology knowledge base"},
    )

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for i, md_file in enumerate(md_files):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            rel_path = str(md_file.relative_to(knowledge_path))
            category = categorize_file(rel_path)

            # Larger chunks for templates/cheatsheets
            is_template = "template" in rel_path.lower() or "cheatsheet" in rel_path.lower()
            cs = 2000 if is_template else 1000
            ov = 400 if is_template else 200

            chunks = chunk_text(content, chunk_size=cs, overlap=ov)
            for j, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({
                    "file": rel_path,
                    "file_name": md_file.name,
                    "chunk_index": j,
                    "category": category,
                })
                ids.append(f"doc_{i}_{j}")
        except Exception as e:
            logger.warning("Error reading %s: %s", md_file, e)

    if documents:
        batch_size = 100
        for start in range(0, len(documents), batch_size):
            end = min(start + batch_size, len(documents))
            collection.add(
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                ids=ids[start:end],
            )

    logger.info("Indexed %d chunks from %d files", len(documents), len(md_files))
    return collection, len(documents), len(md_files)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="RedWeaver Knowledge Service", version="1.0.0")

_collection: Any = None
_doc_count: int = 0
_file_count: int = 0


@app.on_event("startup")
async def startup_event() -> None:
    global _collection, _doc_count, _file_count
    logger.info("Starting knowledge indexing from %s ...", KNOWLEDGE_DATA_PATH)
    _collection, _doc_count, _file_count = build_index(KNOWLEDGE_DATA_PATH)
    if _collection:
        logger.info("Knowledge service ready: %d chunks from %d files", _doc_count, _file_count)
    else:
        logger.warning("Knowledge service started with no data (mount your knowledge directory)")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok" if _collection else "no_data",
        documents_indexed=_doc_count,
        files_indexed=_file_count,
    )


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    if _collection is None:
        return QueryResponse(status="no_data", query=req.query, results_count=0, results=[])

    try:
        where_filter = {"category": req.category} if req.category else None

        results = _collection.query(
            query_texts=[req.query],
            n_results=min(req.top_k, 20),
            where=where_filter,
        )

        entries: list[QueryResult] = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, distances):
                entries.append(QueryResult(
                    content=doc,
                    file=meta.get("file", "unknown"),
                    category=meta.get("category", "general"),
                    relevance_score=round(1.0 - dist, 3) if dist else 1.0,
                ))

        return QueryResponse(status="success", query=req.query, results_count=len(entries), results=entries)

    except Exception as e:
        logger.error("Query failed: %s", e)
        return QueryResponse(status="error", query=req.query, results_count=0, results=[])
