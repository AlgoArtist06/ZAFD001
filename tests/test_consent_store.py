"""Consent must survive a restart.

Consent is a legal fact: losing it on a process restart would 403 every
previously-consented user and erase the record of when they consented. The
durable ledger persists it behind the same seam as the in-memory default; these
tests run the same SQL against SQLite, the offline dialect twin of Postgres.
"""
import sqlite3

from rag.domain.privacy import NOTICE_VERSION
from rag.infrastructure.persistence import DurableConsentLedger


def _ledger(tmp_path):
    db = tmp_path / "app.db"
    return DurableConsentLedger(lambda: sqlite3.connect(db), dialect="sqlite")


def test_recorded_consent_is_reported_with_its_notice_version(tmp_path):
    ledger = _ledger(tmp_path)
    assert ledger.has_consented("user-asha") is False

    record = ledger.record("user-asha")

    assert record.notice_version == NOTICE_VERSION
    assert ledger.has_consented("user-asha") is True
    assert ledger.consent_for("user-asha").notice_version == NOTICE_VERSION


def test_consent_survives_a_process_restart(tmp_path):
    _ledger(tmp_path).record("user-asha")

    # A new ledger instance over the same database is a restarted process.
    restarted = _ledger(tmp_path)

    assert restarted.has_consented("user-asha") is True


def test_re_consent_replaces_the_previous_record(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record("user-asha", notice_version="2026-01-01")
    ledger.record("user-asha", notice_version="2026-06-29")

    assert ledger.consent_for("user-asha").notice_version == "2026-06-29"


def test_erasure_forgets_only_that_users_consent(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record("user-asha")
    ledger.record("user-ravi")

    ledger.erase("user-asha")

    assert ledger.has_consented("user-asha") is False
    assert ledger.has_consented("user-ravi") is True
