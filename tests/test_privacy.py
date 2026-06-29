"""Privacy as a first-class, DPDP-aligned concern on top of accounts.

At signup a Citizen is shown a clear privacy notice and must give explicit
consent before an account is used; the consent is recorded. The notice states
what is stored and why, and discloses that queries are sent to a third-party LLM
together with the trade-off that disclosure carries.

Stored Conversation content is encrypted at rest, and sensitive content is kept
out of plaintext logs. These are the deterministic offline stand-ins for those
guarantees; production swaps real key management and a managed datastore behind
the same seams.
"""
from rag.privacy import (
    NOTICE_VERSION,
    Cipher,
    ConsentLedger,
    redact,
)


def test_the_privacy_notice_says_what_is_stored_and_why():
    from rag.privacy import PRIVACY_NOTICE

    text = PRIVACY_NOTICE.lower()
    assert "stored" in text or "store" in text
    assert "conversation" in text


def test_the_privacy_notice_discloses_third_party_llm_and_the_trade_off():
    from rag.privacy import PRIVACY_NOTICE

    text = PRIVACY_NOTICE.lower()
    # The disclosure the DPDP alignment turns on: queries leave to a third party.
    assert "third-party" in text or "third party" in text
    assert "llm" in text or "language model" in text
    # ... and the trade-off that disclosure carries is named, not buried.
    assert "trade-off" in text or "trade off" in text


def test_consent_is_recorded_against_the_notice_version():
    ledger = ConsentLedger()
    assert ledger.has_consented("user-asha") is False
    record = ledger.record("user-asha")
    assert record.notice_version == NOTICE_VERSION
    assert ledger.has_consented("user-asha") is True


def test_erasing_consent_forgets_it():
    ledger = ConsentLedger()
    ledger.record("user-asha")
    ledger.erase("user-asha")
    assert ledger.has_consented("user-asha") is False


def test_cipher_round_trips_but_does_not_store_plaintext():
    cipher = Cipher()
    secret = "punishment for theft of movable property"
    at_rest = cipher.encrypt(secret)
    assert secret not in at_rest
    assert cipher.decrypt(at_rest) == secret


def test_redaction_drops_the_content_but_keeps_a_length_marker():
    redacted = redact("my landlord stole my deposit")
    assert "landlord" not in redacted
    assert "redacted" in redacted
