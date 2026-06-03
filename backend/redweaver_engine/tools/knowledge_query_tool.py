"""Knowledge query tool for CrewAI agents.

Provides agents with RAG access to the knowledge base via the
standalone knowledge microservice. Queries are sent as HTTP requests.
The backend has NO direct filesystem access to knowledge data.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

KNOWLEDGE_SERVICE_URL = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://knowledge:8100")


class KnowledgeQueryInput(BaseModel):
    """Input schema for knowledge base queries."""

    query: str = Field(description="Search query for the security knowledge base.")
    category: str = Field(
        default="",
        description=(
            "Optional category filter: 'privilege_escalation', 'tunneling', "
            "'flag_hunting', 'web_attacks', 'active_directory', "
            "'reconnaissance', 'exploitation', 'password_attacks', "
            "'reporting', 'c2_frameworks', 'av_evasion', 'cloud_security', 'general'."
        ),
    )
    top_k: int = Field(default=5, description="Number of results to return (1-20).")


class KnowledgeTool(BaseTool):
    """Query the security knowledge base for techniques and procedures.

    Sends queries to the standalone knowledge microservice which maintains
    a vector index of security methodology documents covering reconnaissance,
    exploitation, privilege escalation, tunneling, and more.
    """

    name: str = "knowledge_search"
    description: str = (
        "Query the security knowledge base for penetration testing techniques, "
        "cheatsheets, attack procedures, and exploitation commands. "
        "Categories: privilege_escalation, tunneling, flag_hunting, web_attacks, "
        "active_directory, reconnaissance, exploitation, password_attacks, "
        "reporting, c2_frameworks, av_evasion, cloud_security."
    )
    args_schema: Type[BaseModel] = KnowledgeQueryInput

    def _run(
        self,
        query: str,
        category: str = "",
        top_k: int = 5,
    ) -> str:
        """Query the knowledge service API."""
        try:
            import httpx

            payload: dict[str, Any] = {
                "query": query,
                "top_k": min(max(top_k, 1), 20),
            }
            if category:
                payload["category"] = category

            resp = httpx.post(
                f"{KNOWLEDGE_SERVICE_URL}/query",
                json=payload,
                timeout=30.0,
            )

            if resp.status_code == 200:
                return resp.text
            else:
                return json.dumps({
                    "status": "failed",
                    "error": f"Knowledge service returned HTTP {resp.status_code}",
                })

        except ImportError:
            return json.dumps({
                "status": "failed",
                "error": "httpx not installed. Run: pip install httpx",
            })
        except Exception as e:
            logger.warning("Knowledge service query failed: %s", e)
            return json.dumps({
                "status": "failed",
                "error": f"Knowledge service unavailable: {e}",
            })
