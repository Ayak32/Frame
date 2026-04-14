"""Optional query expansion for vector retrieval only.

Visitor-facing prompts and LLM calls should keep the original query. This module
rewrites text only for create_query_embedding so the query vector aligns with
synonyms and entities that may appear in object/artist embedding text.

Rules are (regex, suffix). First matching rule wins; put more specific patterns first.
"""

from __future__ import annotations

import re
from typing import List, Optional, Pattern, Tuple

Rule = Tuple[Pattern[str], str]

# Suffixes: short noun phrases / names your indexed text might contain. Avoid long prose.
_RETRIEVAL_INTENT_RULES: List[Rule] = [
    (
        re.compile(
            r"\bpointillism\b|neo[-\s]?impressionism\b|\bdivisionism\b",
            re.IGNORECASE,
        ),
        "Neo-Impressionism divisionism optical color Seurat Signac Pissarro Van GoghHenri-Edmond Cross",
    ),
    (
        re.compile(
            r"\bdutch\s+golden\s+age\b|\bnetherlandish\s+(?:golden\s+)?age\b|"
            r"\b17th[-\s]century\s+dutch\b|\bvermeer\s+period\b",
            re.IGNORECASE,
        ),
        "Dutch Republic seventeenth century Rembrandt Vermeer genre painting still life landscape Hals Ruisdael",
    ),
]


def expand_query_for_retrieval(query: str, rules: Optional[List[Rule]] = None) -> str:
    """Return query unchanged, or query + a single tight suffix when a rule matches."""
    if not query or not query.strip():
        return query
    text = query.strip()
    for pattern, suffix in rules or _RETRIEVAL_INTENT_RULES:
        if pattern.search(text):
            return f"{text} {suffix}"
    return text
