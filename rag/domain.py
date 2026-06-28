"""Covered Domain routing.

Retrieval is metadata-filtered and routed by domain first, so a consumer query
does not pull criminal sections. The router maps a query's content words to one
or more Covered Domains (expressed as :class:`ActType` filters). When nothing
matches, it returns every domain - retrieval still runs, but the lexical-overlap
gate downstream is what ultimately decides support vs. Refusal.
"""
from __future__ import annotations

from typing import Dict, List, Set

from ingestion.models import ActType
from rag.text import content_stems

# Domain trigger words, pre-stemmed to match ``content_stems`` output.
_DOMAIN_TRIGGERS: Dict[ActType, Set[str]] = {
    ActType.CRIMINAL: {
        "theft", "steal", "stolen", "thief", "cheat", "cheated", "fraud",
        "dishonest", "police", "arrest", "arrested", "punishment", "offence",
        "crime", "criminal", "fir", "bail", "robbery", "assault",
    },
    ActType.CONSUMER: {
        "consumer", "complaint", "goods", "good", "service", "seller", "shop",
        "shopkeeper", "refund", "product", "defective", "deliver", "delivery",
        "purchase", "buy", "warranty", "commission",
    },
    ActType.IP: {
        "copyright", "patent", "trademark", "infringe", "infringed",
        "infringement", "intellectual", "invention", "brand", "logo",
    },
    ActType.CONSTITUTIONAL: {
        "right", "rights", "liberty", "equality", "life", "freedom",
        "fundamental", "constitution", "constitutional", "discrimination",
        "speech", "personal",
    },
    ActType.SCHEME: {
        "scheme", "yojana", "eligibility", "eligible", "subsidy", "benefit",
        "pension", "welfare", "apply", "application",
    },
}


def route_domains(query: str) -> List[ActType]:
    """Covered Domains a query touches, in stable enum order.

    Returns the matched domains, or all domains when the query matches none.
    """
    stems = set(content_stems(query))
    stemmed_triggers = {
        domain: {s for word in words for s in content_stems(word)}
        for domain, words in _DOMAIN_TRIGGERS.items()
    }
    matched = [
        domain
        for domain in ActType
        if domain in stemmed_triggers and stems & stemmed_triggers[domain]
    ]
    return matched or list(ActType)
