"""The four Covered Domains added in the source expansion.

Cyber (IT Act), transport (Motor Vehicles Act), governance (RTI Act), and
protection (DV + POSH Acts) each route from distinctive trigger words and are
answered from their own statutes end to end. The routing collision guard makes
sure the new triggers did not silently re-route existing gold queries.
"""
import pytest

from ingestion.models import ActType
from tests.doubles import offline_assistant
from rag.domain.routing import route_domains
from rag.services.eval import ENGLISH, load_gold_cases, run_gold_eval


@pytest.mark.parametrize(
    ("query", "domain"),
    [
        ("What is the punishment for online identity theft and hacking?", ActType.CYBER),
        ("What is the challan for driving without a licence?", ActType.TRANSPORT),
        ("How do I file an RTI request for information?", ActType.GOVERNANCE),
        ("What protection order stops domestic violence?", ActType.PROTECTION),
    ],
)
def test_new_domain_queries_route_to_their_domain(query, domain):
    assert domain in route_domains(query)


def test_transport_query_does_not_pull_criminal_theft_sections():
    domains = route_domains("What is the penalty for drunk driving of a motor vehicle?")
    assert ActType.TRANSPORT in domains
    assert ActType.CRIMINAL not in domains


def test_new_domains_are_answered_end_to_end_from_their_own_acts(corpus):
    # Each new act's gold query cites a section from that same act.
    assistant = offline_assistant(corpus)
    new_acts = {"it_act", "mv_act", "rti_act", "dv_act", "posh_act"}
    cases = [c for c in load_gold_cases(language=ENGLISH) if c.expected_act_id in new_acts]
    assert len(cases) == 5, "expected one grounded gold case per new act"
    report = run_gold_eval(assistant, cases)
    assert report.failures == [], report.failures
    assert report.passed == report.total


def test_full_gold_set_still_passes_after_the_expansion(corpus):
    # The whole gold set, existing and new, passes: the new trigger words did
    # not re-route any prior query into a wrong domain.
    cases = load_gold_cases()
    report = run_gold_eval(offline_assistant(corpus), cases)
    assert report.failures == []
    assert report.passed == report.total
